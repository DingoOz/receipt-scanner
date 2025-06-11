import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from .spreadsheet_exporter import SpreadsheetExporter
from .data_formatter import DataFormatter, FormattingOptions
from .export_templates import ExportTemplateManager, ExportTemplate
from .report_generator import ReportGenerator
from ..utils.config import ExportConfig


class BatchExporter:
    """Handles batch export operations with multiple formats and templates."""
    
    def __init__(self, config: ExportConfig):
        """
        Initialize batch exporter.
        
        Args:
            config: Export configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.spreadsheet_exporter = SpreadsheetExporter(config)
        self.template_manager = ExportTemplateManager()
        self.report_generator = ReportGenerator(config.output_directory + "/reports")
        
        # Track export operations
        self.export_history = []
    
    def export_with_multiple_templates(self, ocr_results: List[Dict[str, Any]], 
                                     source_name: str,
                                     template_names: List[str] = None) -> Dict[str, Any]:
        """
        Export data using multiple templates simultaneously.
        
        Args:
            ocr_results: List of OCR processing results
            source_name: Name of the source (folder/album)
            template_names: List of template names to use (all if None)
            
        Returns:
            Dict with batch export results
        """
        try:
            self.logger.info(f"Starting batch export with multiple templates for: {source_name}")
            
            # Get templates to use
            if template_names is None:
                templates = list(self.template_manager.templates.values())
            else:
                templates = []
                for name in template_names:
                    template = self.template_manager.get_template(name)
                    if template:
                        templates.append(template)
                    else:
                        self.logger.warning(f"Template not found: {name}")
            
            if not templates:
                return {
                    'success': False,
                    'error': 'No valid templates found',
                    'exports': []
                }
            
            # Export with each template
            export_results = []
            
            for template in templates:
                try:
                    result = self._export_with_template(ocr_results, source_name, template)
                    export_results.append(result)
                except Exception as e:
                    self.logger.error(f"Export failed for template {template.name}: {str(e)}")
                    export_results.append({
                        'template_name': template.name,
                        'success': False,
                        'error': str(e),
                        'exported_files': []
                    })
            
            # Generate summary
            successful_exports = [r for r in export_results if r.get('success')]
            total_files = sum(len(r.get('exported_files', [])) for r in successful_exports)
            
            return {
                'success': len(successful_exports) > 0,
                'exports': export_results,
                'total_templates': len(templates),
                'successful_templates': len(successful_exports),
                'total_files_exported': total_files,
                'export_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Batch export failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'exports': []
            }
    
    def _export_with_template(self, ocr_results: List[Dict[str, Any]], 
                            source_name: str, template: ExportTemplate) -> Dict[str, Any]:
        """Export data using a specific template."""
        # Create data formatter with template formatting options
        formatter = DataFormatter(template.formatting)
        
        # Format data according to template
        formatted_data = formatter.format_receipts_for_export(ocr_results)
        
        # Apply template field mappings
        mapped_data = self._apply_template_mappings(formatted_data['formatted_receipts'], template)
        
        # Export in template formats
        exported_files = []
        
        for format_type in template.export_formats:
            try:
                if format_type.lower() == 'csv':
                    file_path = self._export_template_csv(mapped_data, source_name, template)
                    exported_files.append(file_path)
                    
                elif format_type.lower() == 'xlsx':
                    file_path = self._export_template_excel(mapped_data, source_name, template)
                    exported_files.append(file_path)
                    
                elif format_type.lower() == 'json':
                    file_path = self._export_template_json(mapped_data, source_name, template)
                    exported_files.append(file_path)
                    
            except Exception as e:
                self.logger.error(f"Failed to export {format_type} for template {template.name}: {str(e)}")
        
        return {
            'template_name': template.name,
            'template_type': template.template_type.value,
            'success': len(exported_files) > 0,
            'exported_files': exported_files,
            'formats': template.export_formats,
            'receipts_processed': len(mapped_data)
        }
    
    def _apply_template_mappings(self, receipts: List[Dict[str, Any]], 
                               template: ExportTemplate) -> List[Dict[str, Any]]:
        """Apply template field mappings to receipt data."""
        mapped_receipts = []
        
        for receipt in receipts:
            mapped_receipt = {}
            
            for field_mapping in template.fields:
                # Extract value using field path
                value = self._get_nested_value(receipt, field_mapping.source_field)
                
                # Apply default if value is empty and default is specified
                if not value and field_mapping.default_value:
                    value = field_mapping.default_value
                
                # Apply formatter if specified
                if value and field_mapping.formatter:
                    value = self._apply_field_formatter(value, field_mapping.formatter)
                
                # Store with export name
                mapped_receipt[field_mapping.export_name] = value
            
            # Add business fields if template has them
            if template.business_fields:
                mapped_receipt.update(template.business_fields)
            
            mapped_receipts.append(mapped_receipt)
        
        # Apply grouping if specified
        if template.group_by:
            mapped_receipts = self._group_mapped_data(mapped_receipts, template.group_by)
        
        # Apply sorting
        mapped_receipts = self._sort_mapped_data(mapped_receipts, template.sort_by)
        
        return mapped_receipts
    
    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        try:
            keys = field_path.split('.')
            value = data
            
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
                
                if value is None:
                    return None
            
            return value
            
        except Exception:
            return None
    
    def _apply_field_formatter(self, value: Any, formatter: str) -> str:
        """Apply formatting to field value."""
        try:
            if formatter == 'currency':
                if isinstance(value, (int, float)):
                    return f"${value:.2f}"
                elif isinstance(value, str) and value.replace('.', '').replace(',', '').isdigit():
                    return f"${float(value):.2f}"
                return str(value)
                
            elif formatter == 'percentage':
                if isinstance(value, (int, float)):
                    return f"{value:.1%}"
                elif isinstance(value, str) and '%' in value:
                    return value
                return str(value)
                
            elif formatter == 'boolean':
                if isinstance(value, bool):
                    return 'Yes' if value else 'No'
                elif isinstance(value, str):
                    return 'Yes' if value.lower() in ['true', 'yes', '1'] else 'No'
                return str(value)
                
            elif formatter == 'items_summary':
                if isinstance(value, list) and value:
                    descriptions = [item.get('description', '') for item in value if item.get('description')]
                    return '; '.join(descriptions[:3])  # First 3 items
                return ''
                
            elif formatter == 'items_business':
                # For business purposes, might categorize items
                if isinstance(value, list) and value:
                    # Simple categorization based on common business items
                    categories = set()
                    for item in value:
                        desc = item.get('description', '').lower()
                        if any(word in desc for word in ['meal', 'food', 'restaurant', 'lunch', 'dinner']):
                            categories.add('Meals')
                        elif any(word in desc for word in ['gas', 'fuel', 'station']):
                            categories.add('Travel')
                        elif any(word in desc for word in ['office', 'supply', 'paper', 'pen']):
                            categories.add('Office Supplies')
                        else:
                            categories.add('General')
                    return '; '.join(categories)
                return 'General'
                
            elif formatter == 'tax_category':
                # Simplified tax categorization
                if isinstance(value, list) and value:
                    # Look for tax-relevant categories
                    for item in value:
                        desc = item.get('description', '').lower()
                        if any(word in desc for word in ['medical', 'pharmacy', 'doctor']):
                            return 'Medical'
                        elif any(word in desc for word in ['office', 'business']):
                            return 'Business Expense'
                        elif any(word in desc for word in ['donation', 'charity']):
                            return 'Charitable'
                return 'General'
                
            elif formatter == 'accounting_code':
                # Simple accounting code assignment
                if isinstance(value, list) and value:
                    # Basic account code mapping
                    for item in value:
                        desc = item.get('description', '').lower()
                        if any(word in desc for word in ['meal', 'food', 'restaurant']):
                            return '6200'  # Meals & Entertainment
                        elif any(word in desc for word in ['gas', 'fuel']):
                            return '6100'  # Travel
                        elif any(word in desc for word in ['office', 'supply']):
                            return '6300'  # Office Supplies
                return '6000'  # General Expense
                
            elif formatter == 'phone':
                # Format phone number
                if isinstance(value, str):
                    digits = ''.join(filter(str.isdigit, value))
                    if len(digits) == 10:
                        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
                return str(value)
                
            else:
                return str(value)
                
        except Exception:
            return str(value) if value else ''
    
    def _group_mapped_data(self, data: List[Dict[str, Any]], group_by: str) -> List[Dict[str, Any]]:
        """Group mapped data by specified field."""
        # For now, just return sorted by group field
        # Could be enhanced to create actual groups
        return sorted(data, key=lambda x: x.get(group_by, ''))
    
    def _sort_mapped_data(self, data: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        """Sort mapped data by specified field."""
        try:
            return sorted(data, key=lambda x: x.get(sort_by, ''))
        except Exception:
            return data
    
    def _export_template_csv(self, mapped_data: List[Dict[str, Any]], 
                           source_name: str, template: ExportTemplate) -> str:
        """Export template data as CSV."""
        import csv
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{template.name.lower().replace(' ', '_')}_{source_name}_{timestamp}.csv"
        file_path = Path(self.config.output_directory) / filename
        
        if mapped_data:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = mapped_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(mapped_data)
        
        return str(file_path)
    
    def _export_template_excel(self, mapped_data: List[Dict[str, Any]], 
                             source_name: str, template: ExportTemplate) -> str:
        """Export template data as Excel."""
        import pandas as pd
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{template.name.lower().replace(' ', '_')}_{source_name}_{timestamp}.xlsx"
        file_path = Path(self.config.output_directory) / filename
        
        if mapped_data:
            df = pd.DataFrame(mapped_data)
            
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=template.name[:31], index=False)  # Sheet name max 31 chars
        
        return str(file_path)
    
    def _export_template_json(self, mapped_data: List[Dict[str, Any]], 
                            source_name: str, template: ExportTemplate) -> str:
        """Export template data as JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{template.name.lower().replace(' ', '_')}_{source_name}_{timestamp}.json"
        file_path = Path(self.config.output_directory) / filename
        
        export_data = {
            'template_info': {
                'name': template.name,
                'description': template.description,
                'type': template.template_type.value,
                'exported_at': datetime.now().isoformat()
            },
            'data': mapped_data
        }
        
        with open(file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False, default=str)
        
        return str(file_path)
    
    def export_comprehensive_package(self, ocr_results: List[Dict[str, Any]], 
                                   source_name: str,
                                   include_reports: bool = True,
                                   include_all_templates: bool = False) -> Dict[str, Any]:
        """
        Create a comprehensive export package with multiple formats and reports.
        
        Args:
            ocr_results: List of OCR processing results
            source_name: Name of the source
            include_reports: Whether to include visual reports
            include_all_templates: Whether to use all available templates
            
        Returns:
            Dict with comprehensive export results
        """
        try:
            self.logger.info(f"Creating comprehensive export package for: {source_name}")
            
            package_results = {
                'source_name': source_name,
                'export_timestamp': datetime.now().isoformat(),
                'spreadsheets': [],
                'reports': [],
                'templates': [],
                'summary': {}
            }
            
            # 1. Standard spreadsheet exports
            standard_export = self.spreadsheet_exporter.export_receipts(ocr_results, source_name)
            if standard_export['success']:
                package_results['spreadsheets'] = standard_export['exported_files']
            
            # 2. Template-based exports
            if include_all_templates:
                template_names = list(self.template_manager.templates.keys())
            else:
                # Use most common templates
                template_names = ['personal_expenses', 'business_expenses', 'detailed_analysis']
            
            template_export = self.export_with_multiple_templates(ocr_results, source_name, template_names)
            if template_export['success']:
                package_results['templates'] = template_export['exports']
            
            # 3. Visual reports
            if include_reports:
                try:
                    report_result = self.report_generator.generate_comprehensive_report(ocr_results, source_name)
                    if report_result['success']:
                        package_results['reports'].append(report_result['report_path'])
                    
                    # Quick charts
                    for chart_type in ['spending_by_merchant', 'spending_over_time']:
                        try:
                            chart_path = self.report_generator.generate_quick_summary_chart(ocr_results, chart_type)
                            package_results['reports'].append(chart_path)
                        except Exception as e:
                            self.logger.warning(f"Chart generation failed for {chart_type}: {str(e)}")
                            
                except Exception as e:
                    self.logger.warning(f"Report generation failed: {str(e)}")
            
            # 4. Summary report
            summary_path = self.spreadsheet_exporter.export_summary_report(ocr_results, source_name)
            package_results['reports'].append(summary_path)
            
            # 5. Package summary
            total_files = (len(package_results['spreadsheets']) + 
                          len(package_results['reports']) +
                          sum(len(t.get('exported_files', [])) for t in package_results['templates']))
            
            package_results['summary'] = {
                'total_files_created': total_files,
                'spreadsheet_files': len(package_results['spreadsheets']),
                'report_files': len(package_results['reports']),
                'template_files': sum(len(t.get('exported_files', [])) for t in package_results['templates']),
                'templates_used': len(package_results['templates']),
                'receipts_processed': len([r for r in ocr_results if r.get('success')]),
                'output_directory': self.config.output_directory
            }
            
            # Record export operation
            self._record_export_operation(package_results)
            
            return {
                'success': True,
                'package': package_results
            }
            
        except Exception as e:
            self.logger.error(f"Comprehensive export failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'package': None
            }
    
    def _record_export_operation(self, package_results: Dict[str, Any]):
        """Record export operation for history tracking."""
        export_record = {
            'timestamp': datetime.now().isoformat(),
            'source_name': package_results['source_name'],
            'files_created': package_results['summary']['total_files_created'],
            'receipts_processed': package_results['summary']['receipts_processed'],
            'export_types': []
        }
        
        if package_results['spreadsheets']:
            export_record['export_types'].append('spreadsheets')
        if package_results['reports']:
            export_record['export_types'].append('reports')
        if package_results['templates']:
            export_record['export_types'].append('templates')
        
        self.export_history.append(export_record)
        
        # Limit history size
        if len(self.export_history) > 100:
            self.export_history = self.export_history[-50:]
    
    def get_export_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent export history."""
        return self.export_history[-limit:] if self.export_history else []
    
    def cleanup_old_exports(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old export files."""
        try:
            output_dir = Path(self.config.output_directory)
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            files_removed = 0
            bytes_freed = 0
            
            for file_path in output_dir.rglob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_date:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        files_removed += 1
                        bytes_freed += file_size
            
            return {
                'success': True,
                'files_removed': files_removed,
                'bytes_freed': bytes_freed,
                'mb_freed': round(bytes_freed / (1024 * 1024), 2)
            }
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }