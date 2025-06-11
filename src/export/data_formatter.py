import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date
from decimal import Decimal
from dataclasses import dataclass

from ..processing.data_extractor import ReceiptData, ReceiptItem


@dataclass
class FormattingOptions:
    """Options for data formatting."""
    currency_symbol: str = '$'
    currency_position: str = 'before'  # 'before' or 'after'
    decimal_places: int = 2
    date_format: str = '%Y-%m-%d'
    time_format: str = '%H:%M'
    percentage_format: str = '.1%'
    include_currency_in_totals: bool = True
    round_amounts: bool = True
    
    # Field visibility
    show_confidence_scores: bool = True
    show_raw_text: bool = False
    show_validation_details: bool = True
    show_processing_metadata: bool = False
    
    # Grouping options
    group_by_merchant: bool = False
    group_by_date: bool = False
    sort_by: str = 'date'  # 'date', 'merchant', 'amount', 'confidence'
    sort_ascending: bool = True


class DataFormatter:
    """Formats receipt data for export with customizable options."""
    
    def __init__(self, options: Optional[FormattingOptions] = None):
        """
        Initialize data formatter.
        
        Args:
            options: Formatting options (uses defaults if None)
        """
        self.options = options or FormattingOptions()
        self.logger = logging.getLogger(__name__)
    
    def format_receipts_for_export(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format receipt data for export.
        
        Args:
            ocr_results: List of OCR processing results
            
        Returns:
            Dict containing formatted data and metadata
        """
        try:
            # Filter and sort receipts
            valid_receipts = self._filter_valid_receipts(ocr_results)
            sorted_receipts = self._sort_receipts(valid_receipts)
            
            # Format individual receipts
            formatted_receipts = []
            for receipt in sorted_receipts:
                formatted_receipt = self._format_single_receipt(receipt)
                formatted_receipts.append(formatted_receipt)
            
            # Generate summary statistics
            summary = self._generate_summary_statistics(formatted_receipts)
            
            # Group receipts if requested
            grouped_data = None
            if self.options.group_by_merchant or self.options.group_by_date:
                grouped_data = self._group_receipts(formatted_receipts)
            
            return {
                'formatted_receipts': formatted_receipts,
                'summary': summary,
                'grouped_data': grouped_data,
                'formatting_options': self.options,
                'total_receipts': len(formatted_receipts),
                'export_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Data formatting failed: {str(e)}")
            raise
    
    def _filter_valid_receipts(self, ocr_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter out invalid receipts."""
        valid_receipts = []
        
        for result in ocr_results:
            if (result.get('success') and 
                result.get('receipt_data') and 
                result['receipt_data'].get('confidence_score', 0) > 0):
                valid_receipts.append(result)
        
        return valid_receipts
    
    def _sort_receipts(self, receipts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort receipts based on options."""
        sort_key_map = {
            'date': lambda r: self._get_sort_date(r),
            'merchant': lambda r: r['receipt_data'].get('merchant_name', '').lower(),
            'amount': lambda r: float(r['receipt_data'].get('total_amount', 0)) if r['receipt_data'].get('total_amount') else 0,
            'confidence': lambda r: r['receipt_data'].get('confidence_score', 0)
        }
        
        sort_key = sort_key_map.get(self.options.sort_by, sort_key_map['date'])
        
        return sorted(receipts, key=sort_key, reverse=not self.options.sort_ascending)
    
    def _get_sort_date(self, receipt: Dict[str, Any]) -> date:
        """Get date for sorting purposes."""
        receipt_date = receipt['receipt_data'].get('date')
        if isinstance(receipt_date, str):
            try:
                return datetime.fromisoformat(receipt_date).date()
            except:
                return date.min
        elif isinstance(receipt_date, date):
            return receipt_date
        else:
            return date.min
    
    def _format_single_receipt(self, receipt: Dict[str, Any]) -> Dict[str, Any]:
        """Format a single receipt."""
        receipt_data = receipt['receipt_data']
        
        formatted = {
            'file_info': {
                'file_name': receipt.get('file_name', 'Unknown'),
                'file_id': receipt.get('file_id', ''),
            },
            'merchant': {
                'name': receipt_data.get('merchant_name', ''),
                'address': receipt_data.get('merchant_address', ''),
                'phone': self._format_phone(receipt_data.get('merchant_phone')),
            },
            'transaction': {
                'date': self._format_date(receipt_data.get('date')),
                'time': self._format_time(receipt_data.get('time')),
                'receipt_number': receipt_data.get('receipt_number', ''),
            },
            'amounts': {
                'subtotal': self._format_currency(receipt_data.get('subtotal')),
                'tax': self._format_currency(receipt_data.get('tax_amount')),
                'tip': self._format_currency(receipt_data.get('tip_amount')),
                'total': self._format_currency(receipt_data.get('total_amount')),
            },
            'payment': {
                'method': receipt_data.get('payment_method', ''),
                'card_last_four': receipt_data.get('card_last_four', ''),
            },
            'items': self._format_items(receipt_data.get('items', [])),
            'metadata': {
                'items_count': len(receipt_data.get('items', [])),
                'ocr_method': receipt.get('ocr_method', ''),
                'processing_time': receipt.get('processing_time', 0),
            }
        }
        
        # Add confidence scores if enabled
        if self.options.show_confidence_scores:
            formatted['confidence'] = {
                'ocr_confidence': self._format_percentage(receipt.get('ocr_confidence', 0)),
                'validation_confidence': self._format_percentage(receipt_data.get('confidence_score', 0)),
                'overall_confidence': self._format_percentage(
                    (receipt.get('ocr_confidence', 0) + receipt_data.get('confidence_score', 0)) / 2
                )
            }
        
        # Add validation details if enabled
        if self.options.show_validation_details and 'validation' in receipt:
            validation = receipt['validation']
            formatted['validation'] = {
                'is_valid': validation.get('is_valid', False),
                'confidence_score': self._format_percentage(validation.get('confidence_score', 0)),
                'issues_count': len(validation.get('issues', [])),
                'warnings_count': len(validation.get('warnings', [])),
            }
            
            # Include detailed issues if requested
            if validation.get('issues'):
                formatted['validation']['issues'] = [
                    {
                        'type': issue.get('type', ''),
                        'severity': issue.get('severity', ''),
                        'message': issue.get('message', '')
                    }
                    for issue in validation['issues']
                ]
        
        # Add raw text if enabled
        if self.options.show_raw_text:
            formatted['raw_text'] = receipt.get('raw_text', '')
        
        # Add processing metadata if enabled
        if self.options.show_processing_metadata:
            formatted['processing'] = {
                'quality_metrics': receipt.get('quality_metrics', {}),
                'preprocessing_applied': receipt.get('preprocessing_applied', False),
                'processing_timestamp': receipt.get('processing_timestamp', ''),
            }
        
        return formatted
    
    def _format_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format receipt items."""
        formatted_items = []
        
        for item in items:
            formatted_item = {
                'description': item.get('description', ''),
                'quantity': self._format_quantity(item.get('quantity')),
                'unit_price': self._format_currency(item.get('unit_price')),
                'total_price': self._format_currency(item.get('total_price')),
            }
            
            if self.options.show_confidence_scores:
                formatted_item['confidence'] = self._format_percentage(item.get('confidence', 0))
            
            formatted_items.append(formatted_item)
        
        return formatted_items
    
    def _format_currency(self, amount: Union[str, float, Decimal, None]) -> str:
        """Format currency amount."""
        if amount is None or amount == '':
            return ''
        
        try:
            # Convert to float
            if isinstance(amount, str):
                # Remove currency symbols and commas
                cleaned = amount.replace('$', '').replace(',', '').strip()
                if not cleaned:
                    return ''
                amount_float = float(cleaned)
            elif isinstance(amount, Decimal):
                amount_float = float(amount)
            else:
                amount_float = float(amount)
            
            # Round if requested
            if self.options.round_amounts:
                amount_float = round(amount_float, self.options.decimal_places)
            
            # Format with decimal places
            formatted_amount = f"{amount_float:.{self.options.decimal_places}f}"
            
            # Add currency symbol
            if self.options.include_currency_in_totals:
                if self.options.currency_position == 'before':
                    return f"{self.options.currency_symbol}{formatted_amount}"
                else:
                    return f"{formatted_amount}{self.options.currency_symbol}"
            else:
                return formatted_amount
                
        except (ValueError, TypeError):
            return str(amount) if amount else ''
    
    def _format_date(self, date_value: Union[str, date, None]) -> str:
        """Format date."""
        if not date_value:
            return ''
        
        try:
            if isinstance(date_value, str):
                # Try to parse ISO format first
                try:
                    parsed_date = datetime.fromisoformat(date_value).date()
                except:
                    # Try other common formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y']:
                        try:
                            parsed_date = datetime.strptime(date_value, fmt).date()
                            break
                        except:
                            continue
                    else:
                        return date_value  # Return as-is if can't parse
            else:
                parsed_date = date_value
            
            return parsed_date.strftime(self.options.date_format)
            
        except Exception:
            return str(date_value) if date_value else ''
    
    def _format_time(self, time_value: Union[str, None]) -> str:
        """Format time."""
        if not time_value:
            return ''
        
        try:
            # Simple time formatting - could be enhanced
            return str(time_value)
        except:
            return ''
    
    def _format_phone(self, phone: Union[str, None]) -> str:
        """Format phone number."""
        if not phone:
            return ''
        
        # Simple phone formatting
        digits = ''.join(filter(str.isdigit, phone))
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone
    
    def _format_quantity(self, quantity: Union[str, float, int, None]) -> str:
        """Format quantity."""
        if quantity is None or quantity == '':
            return ''
        
        try:
            qty_float = float(quantity)
            # Show as integer if it's a whole number
            if qty_float == int(qty_float):
                return str(int(qty_float))
            else:
                return f"{qty_float:.2f}"
        except:
            return str(quantity)
    
    def _format_percentage(self, value: Union[float, int, None]) -> str:
        """Format percentage."""
        if value is None:
            return ''
        
        try:
            return f"{float(value):{self.options.percentage_format}}"
        except:
            return str(value)
    
    def _generate_summary_statistics(self, formatted_receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not formatted_receipts:
            return {}
        
        total_amount = 0.0
        total_tax = 0.0
        total_tip = 0.0
        merchants = set()
        dates = []
        item_counts = []
        confidence_scores = []
        
        for receipt in formatted_receipts:
            # Extract numeric values from formatted currency
            total_str = receipt['amounts']['total']
            if total_str:
                try:
                    total_amount += float(total_str.replace(self.options.currency_symbol, '').replace(',', ''))
                except:
                    pass
            
            tax_str = receipt['amounts']['tax']
            if tax_str:
                try:
                    total_tax += float(tax_str.replace(self.options.currency_symbol, '').replace(',', ''))
                except:
                    pass
            
            tip_str = receipt['amounts']['tip']
            if tip_str:
                try:
                    total_tip += float(tip_str.replace(self.options.currency_symbol, '').replace(',', ''))
                except:
                    pass
            
            if receipt['merchant']['name']:
                merchants.add(receipt['merchant']['name'])
            
            if receipt['transaction']['date']:
                dates.append(receipt['transaction']['date'])
            
            item_counts.append(receipt['metadata']['items_count'])
            
            if self.options.show_confidence_scores and 'confidence' in receipt:
                conf_str = receipt['confidence']['validation_confidence']
                try:
                    conf_val = float(conf_str.replace('%', '')) / 100
                    confidence_scores.append(conf_val)
                except:
                    pass
        
        summary = {
            'totals': {
                'amount': self._format_currency(total_amount),
                'tax': self._format_currency(total_tax),
                'tip': self._format_currency(total_tip),
                'receipts_count': len(formatted_receipts),
                'unique_merchants': len(merchants),
                'total_items': sum(item_counts),
            },
            'averages': {
                'amount_per_receipt': self._format_currency(total_amount / len(formatted_receipts)) if formatted_receipts else self._format_currency(0),
                'items_per_receipt': round(sum(item_counts) / len(formatted_receipts), 1) if formatted_receipts else 0,
            },
            'date_range': {
                'earliest': min(dates) if dates else '',
                'latest': max(dates) if dates else '',
            },
            'merchants': list(merchants)
        }
        
        if confidence_scores:
            summary['quality'] = {
                'average_confidence': self._format_percentage(sum(confidence_scores) / len(confidence_scores)),
                'min_confidence': self._format_percentage(min(confidence_scores)),
                'max_confidence': self._format_percentage(max(confidence_scores)),
            }
        
        return summary
    
    def _group_receipts(self, formatted_receipts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Group receipts by merchant or date."""
        grouped = {}
        
        if self.options.group_by_merchant:
            merchant_groups = {}
            for receipt in formatted_receipts:
                merchant = receipt['merchant']['name'] or 'Unknown'
                if merchant not in merchant_groups:
                    merchant_groups[merchant] = []
                merchant_groups[merchant].append(receipt)
            grouped['by_merchant'] = merchant_groups
        
        if self.options.group_by_date:
            date_groups = {}
            for receipt in formatted_receipts:
                date_str = receipt['transaction']['date'] or 'Unknown'
                if date_str not in date_groups:
                    date_groups[date_str] = []
                date_groups[date_str].append(receipt)
            grouped['by_date'] = date_groups
        
        return grouped
    
    def create_export_filename(self, base_name: str, format_type: str, include_timestamp: bool = True) -> str:
        """Create standardized export filename."""
        # Clean base name
        clean_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_name = clean_name.replace(' ', '_')
        
        # Add timestamp if requested
        if include_timestamp:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{clean_name}_{timestamp}.{format_type}"
        else:
            filename = f"{clean_name}.{format_type}"
        
        return filename