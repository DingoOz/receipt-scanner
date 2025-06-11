import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from .data_formatter import FormattingOptions


class TemplateType(Enum):
    """Types of export templates."""
    PERSONAL = "personal"
    BUSINESS = "business"
    EXPENSE_REPORT = "expense_report"
    TAX_PREPARATION = "tax_preparation"
    ACCOUNTING = "accounting"
    CUSTOM = "custom"


@dataclass
class FieldMapping:
    """Mapping configuration for a field."""
    source_field: str  # Path to field in receipt data (e.g., "merchant.name")
    export_name: str   # Name in export
    required: bool = False
    default_value: str = ""
    formatter: Optional[str] = None  # "currency", "date", "percentage", etc.
    validation_rule: Optional[str] = None


@dataclass
class ExportTemplate:
    """Template for customizing export format and content."""
    name: str
    description: str
    template_type: TemplateType
    
    # Field mappings
    fields: List[FieldMapping]
    
    # Formatting options
    formatting: FormattingOptions
    
    # Template-specific settings
    include_summary: bool = True
    include_items_detail: bool = True
    group_by: Optional[str] = None  # "merchant", "date", "category"
    sort_by: str = "date"
    
    # Export options
    export_formats: List[str] = None  # ["csv", "xlsx", "json"]
    filename_template: str = "{template_name}_{source}_{timestamp}"
    
    # Business-specific fields
    business_fields: Optional[Dict[str, Any]] = None
    
    # Custom calculations
    custom_calculations: Optional[List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.export_formats is None:
            self.export_formats = ["xlsx"]


class ExportTemplateManager:
    """Manages export templates and configurations."""
    
    def __init__(self, templates_dir: str = "config/templates"):
        """
        Initialize template manager.
        
        Args:
            templates_dir: Directory containing template files
        """
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Load built-in templates
        self.templates = self._load_builtin_templates()
        
        # Load custom templates
        self._load_custom_templates()
    
    def _load_builtin_templates(self) -> Dict[str, ExportTemplate]:
        """Load built-in export templates."""
        templates = {}
        
        # Personal expense tracking template
        templates["personal_expenses"] = ExportTemplate(
            name="Personal Expenses",
            description="Template for personal expense tracking",
            template_type=TemplateType.PERSONAL,
            fields=[
                FieldMapping("transaction.date", "Date", required=True, formatter="date"),
                FieldMapping("merchant.name", "Merchant", required=True),
                FieldMapping("amounts.total", "Amount", required=True, formatter="currency"),
                FieldMapping("amounts.tax", "Tax", formatter="currency"),
                FieldMapping("payment.method", "Payment Method"),
                FieldMapping("items", "Description", formatter="items_summary"),
                FieldMapping("metadata.items_count", "Items Count"),
                FieldMapping("confidence.validation_confidence", "Confidence", formatter="percentage")
            ],
            formatting=FormattingOptions(
                date_format='%m/%d/%Y',
                include_currency_in_totals=True,
                show_confidence_scores=True
            ),
            sort_by="date",
            export_formats=["xlsx", "csv"]
        )
        
        # Business expense report template
        templates["business_expenses"] = ExportTemplate(
            name="Business Expense Report",
            description="Template for business expense reporting",
            template_type=TemplateType.BUSINESS,
            fields=[
                FieldMapping("transaction.date", "Date", required=True, formatter="date"),
                FieldMapping("merchant.name", "Vendor", required=True),
                FieldMapping("merchant.address", "Vendor Address"),
                FieldMapping("amounts.subtotal", "Subtotal", formatter="currency"),
                FieldMapping("amounts.tax", "Tax Amount", formatter="currency"),
                FieldMapping("amounts.total", "Total", required=True, formatter="currency"),
                FieldMapping("payment.method", "Payment Method"),
                FieldMapping("transaction.receipt_number", "Receipt Number"),
                FieldMapping("items", "Business Purpose", formatter="items_business"),
                FieldMapping("validation.is_valid", "Valid Receipt", formatter="boolean")
            ],
            formatting=FormattingOptions(
                date_format='%Y-%m-%d',
                include_currency_in_totals=True,
                show_confidence_scores=False,
                show_validation_details=True
            ),
            include_summary=True,
            group_by="merchant",
            export_formats=["xlsx", "csv", "json"],
            business_fields={
                "employee_name": "",
                "department": "",
                "project_code": "",
                "approval_status": "Pending"
            }
        )
        
        # Tax preparation template
        templates["tax_preparation"] = ExportTemplate(
            name="Tax Preparation",
            description="Template optimized for tax preparation",
            template_type=TemplateType.TAX_PREPARATION,
            fields=[
                FieldMapping("transaction.date", "Date", required=True, formatter="date"),
                FieldMapping("merchant.name", "Payee", required=True),
                FieldMapping("amounts.total", "Amount", required=True, formatter="currency"),
                FieldMapping("amounts.tax", "Sales Tax", formatter="currency"),
                FieldMapping("payment.method", "Payment Type"),
                FieldMapping("items", "Expense Category", formatter="tax_category"),
                FieldMapping("merchant.address", "Location"),
                FieldMapping("validation.is_valid", "Verified", formatter="boolean")
            ],
            formatting=FormattingOptions(
                date_format='%m/%d/%Y',
                include_currency_in_totals=True,
                show_confidence_scores=False,
                show_validation_details=True
            ),
            group_by="date",
            sort_by="date",
            export_formats=["xlsx", "csv"],
            custom_calculations=[
                {
                    "name": "quarterly_total",
                    "description": "Quarterly spending total",
                    "formula": "sum_by_quarter(amounts.total)"
                },
                {
                    "name": "deductible_amount",
                    "description": "Potentially deductible amount",
                    "formula": "sum_business_expenses()"
                }
            ]
        )
        
        # Accounting template
        templates["accounting"] = ExportTemplate(
            name="Accounting Integration",
            description="Template for accounting software integration",
            template_type=TemplateType.ACCOUNTING,
            fields=[
                FieldMapping("transaction.date", "Transaction Date", required=True, formatter="date"),
                FieldMapping("merchant.name", "Vendor Name", required=True),
                FieldMapping("amounts.total", "Amount", required=True, formatter="currency"),
                FieldMapping("amounts.tax", "Tax Amount", formatter="currency"),
                FieldMapping("payment.method", "Payment Account"),
                FieldMapping("items", "Account Code", formatter="accounting_code"),
                FieldMapping("transaction.receipt_number", "Reference"),
                FieldMapping("merchant.address", "Vendor Address"),
                FieldMapping("file_info.file_name", "Source Document")
            ],
            formatting=FormattingOptions(
                date_format='%Y-%m-%d',
                include_currency_in_totals=False,  # Numbers only for accounting
                show_confidence_scores=False,
                decimal_places=2
            ),
            include_items_detail=True,
            export_formats=["csv", "json"]
        )
        
        # Detailed analysis template
        templates["detailed_analysis"] = ExportTemplate(
            name="Detailed Analysis",
            description="Comprehensive template with all available data",
            template_type=TemplateType.CUSTOM,
            fields=[
                FieldMapping("file_info.file_name", "Source File"),
                FieldMapping("transaction.date", "Date", formatter="date"),
                FieldMapping("transaction.time", "Time"),
                FieldMapping("merchant.name", "Merchant"),
                FieldMapping("merchant.address", "Address"),
                FieldMapping("merchant.phone", "Phone", formatter="phone"),
                FieldMapping("amounts.subtotal", "Subtotal", formatter="currency"),
                FieldMapping("amounts.tax", "Tax", formatter="currency"),
                FieldMapping("amounts.tip", "Tip", formatter="currency"),
                FieldMapping("amounts.total", "Total", formatter="currency"),
                FieldMapping("payment.method", "Payment Method"),
                FieldMapping("payment.card_last_four", "Card Last 4"),
                FieldMapping("transaction.receipt_number", "Receipt #"),
                FieldMapping("metadata.items_count", "Items Count"),
                FieldMapping("metadata.ocr_method", "OCR Method"),
                FieldMapping("confidence.ocr_confidence", "OCR Confidence", formatter="percentage"),
                FieldMapping("confidence.validation_confidence", "Validation Confidence", formatter="percentage"),
                FieldMapping("validation.is_valid", "Valid", formatter="boolean")
            ],
            formatting=FormattingOptions(
                show_confidence_scores=True,
                show_validation_details=True,
                show_processing_metadata=True
            ),
            include_summary=True,
            include_items_detail=True,
            export_formats=["xlsx", "json"]
        )
        
        return templates
    
    def _load_custom_templates(self):
        """Load custom templates from files."""
        template_files = self.templates_dir.glob("*.json")
        
        for template_file in template_files:
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                
                template = self._dict_to_template(template_data)
                self.templates[template.name.lower().replace(" ", "_")] = template
                
                self.logger.info(f"Loaded custom template: {template.name}")
                
            except Exception as e:
                self.logger.warning(f"Failed to load template {template_file}: {str(e)}")
    
    def _dict_to_template(self, data: Dict[str, Any]) -> ExportTemplate:
        """Convert dictionary to ExportTemplate object."""
        # Convert fields
        fields = []
        for field_data in data.get('fields', []):
            field = FieldMapping(**field_data)
            fields.append(field)
        
        # Convert formatting options
        formatting_data = data.get('formatting', {})
        formatting = FormattingOptions(**formatting_data)
        
        # Convert template type
        template_type = TemplateType(data.get('template_type', 'custom'))
        
        # Create template
        template_data = data.copy()
        template_data['fields'] = fields
        template_data['formatting'] = formatting
        template_data['template_type'] = template_type
        
        return ExportTemplate(**template_data)
    
    def get_template(self, template_name: str) -> Optional[ExportTemplate]:
        """Get template by name."""
        return self.templates.get(template_name.lower().replace(" ", "_"))
    
    def list_templates(self) -> List[Dict[str, str]]:
        """List available templates."""
        return [
            {
                "name": template.name,
                "key": key,
                "description": template.description,
                "type": template.template_type.value,
                "formats": ", ".join(template.export_formats)
            }
            for key, template in self.templates.items()
        ]
    
    def save_custom_template(self, template: ExportTemplate) -> bool:
        """Save a custom template to file."""
        try:
            template_file = self.templates_dir / f"{template.name.lower().replace(' ', '_')}.json"
            
            # Convert to dictionary
            template_dict = asdict(template)
            
            # Convert enum to string
            template_dict['template_type'] = template.template_type.value
            
            # Save to file
            with open(template_file, 'w', encoding='utf-8') as f:
                json.dump(template_dict, f, indent=2, ensure_ascii=False)
            
            # Add to loaded templates
            self.templates[template.name.lower().replace(" ", "_")] = template
            
            self.logger.info(f"Saved custom template: {template.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save template: {str(e)}")
            return False
    
    def create_template_from_config(self, name: str, description: str, 
                                  template_type: TemplateType, 
                                  field_config: List[Dict[str, Any]], 
                                  formatting_config: Dict[str, Any] = None) -> ExportTemplate:
        """Create a new template from configuration."""
        # Convert field configurations
        fields = []
        for field_config_item in field_config:
            field = FieldMapping(**field_config_item)
            fields.append(field)
        
        # Create formatting options
        formatting = FormattingOptions(**(formatting_config or {}))
        
        # Create template
        template = ExportTemplate(
            name=name,
            description=description,
            template_type=template_type,
            fields=fields,
            formatting=formatting
        )
        
        return template
    
    def get_field_suggestions(self) -> Dict[str, List[str]]:
        """Get suggestions for field mappings."""
        return {
            "merchant": [
                "merchant.name",
                "merchant.address", 
                "merchant.phone"
            ],
            "transaction": [
                "transaction.date",
                "transaction.time",
                "transaction.receipt_number"
            ],
            "amounts": [
                "amounts.subtotal",
                "amounts.tax",
                "amounts.tip",
                "amounts.total"
            ],
            "payment": [
                "payment.method",
                "payment.card_last_four"
            ],
            "items": [
                "items",
                "metadata.items_count"
            ],
            "quality": [
                "confidence.ocr_confidence",
                "confidence.validation_confidence",
                "validation.is_valid"
            ],
            "metadata": [
                "file_info.file_name",
                "file_info.file_id",
                "metadata.ocr_method",
                "metadata.processing_time"
            ]
        }
    
    def validate_template(self, template: ExportTemplate) -> Dict[str, Any]:
        """Validate template configuration."""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required fields
        if not template.name:
            validation_result["errors"].append("Template name is required")
        
        if not template.fields:
            validation_result["errors"].append("At least one field mapping is required")
        
        # Check field mappings
        for field in template.fields:
            if not field.source_field:
                validation_result["errors"].append(f"Source field is required for '{field.export_name}'")
            
            if not field.export_name:
                validation_result["errors"].append(f"Export name is required for field '{field.source_field}'")
        
        # Check export formats
        valid_formats = {"csv", "xlsx", "json"}
        for fmt in template.export_formats:
            if fmt not in valid_formats:
                validation_result["warnings"].append(f"Unknown export format: {fmt}")
        
        # Set overall validity
        validation_result["is_valid"] = len(validation_result["errors"]) == 0
        
        return validation_result