import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from .data_extractor import ReceiptData, ReceiptItem


class ReceiptParser:
    """Advanced receipt parser with merchant-specific templates and validation."""
    
    def __init__(self):
        """Initialize receipt parser with templates."""
        self.logger = logging.getLogger(__name__)
        self.merchant_templates = self._load_merchant_templates()
        self.common_items = self._load_common_items()
    
    def _load_merchant_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load merchant-specific parsing templates."""
        return {
            'walmart': {
                'name_patterns': [r'walmart.*supercenter', r'walmart.*store'],
                'item_patterns': [
                    re.compile(r'^([A-Z0-9\s]+)\s+(\d{12})\s*([TNX])\s*(\d+\.\d{2})$', re.MULTILINE),
                    re.compile(r'^([A-Z0-9\s]+)\s+(\d+\.\d{2})\s*([TNX])$', re.MULTILINE),
                ],
                'total_pattern': re.compile(r'total\s*(\d+\.\d{2})', re.IGNORECASE),
                'tax_pattern': re.compile(r'tax\s*(\d+\.\d{2})', re.IGNORECASE),
            },
            'target': {
                'name_patterns': [r'target', r'target.*store'],
                'item_patterns': [
                    re.compile(r'^(.+?)\s+(\d{3}-\d{2}-\d{4})\s*(\d+\.\d{2})\s*([TNX])$', re.MULTILINE),
                ],
                'total_pattern': re.compile(r'total\s*(\d+\.\d{2})', re.IGNORECASE),
            },
            'costco': {
                'name_patterns': [r'costco.*wholesale'],
                'item_patterns': [
                    re.compile(r'^(\d+)\s+(.+?)\s+(\d+\.\d{2})$', re.MULTILINE),
                ],
                'total_pattern': re.compile(r'total\s*(\d+\.\d{2})', re.IGNORECASE),
            },
            'grocery': {
                'name_patterns': [r'kroger', r'safeway', r'publix', r'whole foods', r'trader.*joe'],
                'item_patterns': [
                    re.compile(r'^(.+?)\s+(\d+\.\d{2})\s*([FT])$', re.MULTILINE),
                    re.compile(r'^(.+?)\s+(\d+\.\d{2})$', re.MULTILINE),
                ],
                'total_pattern': re.compile(r'total\s*(\d+\.\d{2})', re.IGNORECASE),
            },
            'restaurant': {
                'name_patterns': [r'mcdonald', r'burger.*king', r'subway', r'starbucks', r'pizza'],
                'item_patterns': [
                    re.compile(r'^(\d+)\s*x\s*(.+?)\s+(\d+\.\d{2})$', re.MULTILINE),
                    re.compile(r'^(.+?)\s+(\d+\.\d{2})$', re.MULTILINE),
                ],
                'total_pattern': re.compile(r'total\s*(\d+\.\d{2})', re.IGNORECASE),
                'tip_pattern': re.compile(r'tip\s*(\d+\.\d{2})', re.IGNORECASE),
            }
        }
    
    def _load_common_items(self) -> Dict[str, List[str]]:
        """Load common item categories and keywords."""
        return {
            'food': [
                'milk', 'bread', 'eggs', 'cheese', 'butter', 'yogurt', 'meat', 'chicken', 'beef',
                'fish', 'salmon', 'fruit', 'apple', 'banana', 'orange', 'vegetable', 'tomato',
                'potato', 'onion', 'lettuce', 'cereal', 'pasta', 'rice', 'beans', 'soup'
            ],
            'beverages': [
                'water', 'soda', 'juice', 'coffee', 'tea', 'beer', 'wine', 'energy drink'
            ],
            'household': [
                'detergent', 'shampoo', 'soap', 'toothpaste', 'toilet paper', 'paper towel',
                'cleaner', 'dish soap', 'trash bag'
            ],
            'pharmacy': [
                'medicine', 'vitamin', 'aspirin', 'bandaid', 'thermometer', 'prescription'
            ],
            'clothing': [
                'shirt', 'pants', 'shoes', 'dress', 'jacket', 'socks', 'underwear'
            ],
            'electronics': [
                'phone', 'charger', 'battery', 'cable', 'headphone', 'speaker'
            ]
        }
    
    def parse_receipt_advanced(self, text: str, basic_receipt: ReceiptData) -> ReceiptData:
        """
        Apply advanced parsing with merchant templates and validation.
        
        Args:
            text: Raw OCR text
            basic_receipt: Basic receipt data from general parser
            
        Returns:
            Enhanced ReceiptData with improved parsing
        """
        try:
            # Start with basic receipt
            enhanced_receipt = basic_receipt
            
            # Identify merchant template
            merchant_type = self._identify_merchant_type(text)
            if merchant_type:
                self.logger.debug(f"Identified merchant type: {merchant_type}")
                enhanced_receipt = self._apply_merchant_template(text, enhanced_receipt, merchant_type)
            
            # Enhance item parsing
            enhanced_receipt.items = self._enhance_item_parsing(text, enhanced_receipt.items)
            
            # Validate and correct data
            enhanced_receipt = self._validate_and_correct(enhanced_receipt)
            
            # Categorize items
            self._categorize_items(enhanced_receipt.items)
            
            # Recalculate confidence
            enhanced_receipt.confidence_score = self._calculate_enhanced_confidence(enhanced_receipt)
            
            return enhanced_receipt
            
        except Exception as e:
            self.logger.error(f"Advanced parsing failed: {str(e)}")
            return basic_receipt
    
    def _identify_merchant_type(self, text: str) -> Optional[str]:
        """Identify merchant type from text."""
        text_lower = text.lower()
        
        for merchant_type, template in self.merchant_templates.items():
            for pattern in template['name_patterns']:
                if re.search(pattern, text_lower):
                    return merchant_type
        
        return None
    
    def _apply_merchant_template(self, text: str, receipt: ReceiptData, merchant_type: str) -> ReceiptData:
        """Apply merchant-specific parsing template."""
        template = self.merchant_templates[merchant_type]
        
        # Try merchant-specific item patterns
        items = []
        for pattern in template['item_patterns']:
            matches = pattern.findall(text)
            for match in matches:
                item = self._parse_merchant_item(match, merchant_type)
                if item:
                    items.append(item)
        
        if items:
            receipt.items = items
        
        # Try merchant-specific total pattern
        if 'total_pattern' in template:
            total_match = template['total_pattern'].search(text)
            if total_match:
                try:
                    receipt.total_amount = Decimal(total_match.group(1))
                except InvalidOperation:
                    pass
        
        # Try merchant-specific tax pattern
        if 'tax_pattern' in template:
            tax_match = template['tax_pattern'].search(text)
            if tax_match:
                try:
                    receipt.tax_amount = Decimal(tax_match.group(1))
                except InvalidOperation:
                    pass
        
        # Try merchant-specific tip pattern (restaurants)
        if 'tip_pattern' in template:
            tip_match = template['tip_pattern'].search(text)
            if tip_match:
                try:
                    receipt.tip_amount = Decimal(tip_match.group(1))
                except InvalidOperation:
                    pass
        
        return receipt
    
    def _parse_merchant_item(self, match: Tuple, merchant_type: str) -> Optional[ReceiptItem]:
        """Parse item based on merchant-specific format."""
        try:
            if merchant_type == 'walmart':
                if len(match) == 4:
                    # (description, upc, tax_code, price)
                    description = match[0].strip()
                    price = Decimal(match[3])
                    return ReceiptItem(description=description, total_price=price, confidence=0.9)
                elif len(match) == 3:
                    # (description, price, tax_code)
                    description = match[0].strip()
                    price = Decimal(match[1])
                    return ReceiptItem(description=description, total_price=price, confidence=0.9)
            
            elif merchant_type == 'target':
                if len(match) == 4:
                    # (description, dpci, price, tax_code)
                    description = match[0].strip()
                    price = Decimal(match[2])
                    return ReceiptItem(description=description, total_price=price, confidence=0.9)
            
            elif merchant_type == 'costco':
                if len(match) == 3:
                    # (quantity, description, price)
                    quantity = float(match[0]) if match[0].isdigit() else 1.0
                    description = match[1].strip()
                    total_price = Decimal(match[2])
                    unit_price = total_price / Decimal(str(quantity)) if quantity > 0 else total_price
                    return ReceiptItem(
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_price=total_price,
                        confidence=0.9
                    )
            
            elif merchant_type in ['grocery', 'restaurant']:
                if len(match) >= 2:
                    if match[0].isdigit():
                        # (quantity, description, price)
                        quantity = float(match[0])
                        description = match[1].strip()
                        total_price = Decimal(match[2])
                        unit_price = total_price / Decimal(str(quantity)) if quantity > 0 else total_price
                        return ReceiptItem(
                            description=description,
                            quantity=quantity,
                            unit_price=unit_price,
                            total_price=total_price,
                            confidence=0.9
                        )
                    else:
                        # (description, price)
                        description = match[0].strip()
                        price = Decimal(match[1])
                        return ReceiptItem(description=description, total_price=price, confidence=0.8)
        
        except (ValueError, InvalidOperation, IndexError) as e:
            self.logger.debug(f"Failed to parse merchant item: {str(e)}")
        
        return None
    
    def _enhance_item_parsing(self, text: str, existing_items: List[ReceiptItem]) -> List[ReceiptItem]:
        """Enhance item parsing with additional techniques."""
        enhanced_items = existing_items.copy()
        
        # Try to extract missed items using additional patterns
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Skip if line is already captured
            if any(item.description.lower() in line.lower() for item in enhanced_items):
                continue
            
            # Try additional item patterns
            item = self._try_additional_patterns(line)
            if item:
                enhanced_items.append(item)
        
        # Remove duplicates and invalid items
        enhanced_items = self._deduplicate_items(enhanced_items)
        
        return enhanced_items
    
    def _try_additional_patterns(self, line: str) -> Optional[ReceiptItem]:
        """Try additional patterns for item extraction."""
        patterns = [
            # Pattern: ITEM NAME $X.XX
            re.compile(r'^([A-Z][A-Z\s&]+)\s+\$(\d+\.\d{2})$'),
            # Pattern: Item name with special chars $X.XX
            re.compile(r'^([A-Za-z][A-Za-z\s\-&\'\.]+)\s+\$?(\d+\.\d{2})$'),
            # Pattern: QTY @ $X.XX = $Y.YY
            re.compile(r'^(\d+)\s*@\s*\$?(\d+\.\d{2})\s*=\s*\$?(\d+\.\d{2})$'),
        ]
        
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                try:
                    groups = match.groups()
                    if len(groups) == 2:
                        # Simple description + price
                        description = groups[0].strip()
                        if len(description) > 2 and self._is_valid_item_description(description):
                            price = Decimal(groups[1])
                            return ReceiptItem(description=description, total_price=price, confidence=0.7)
                    
                    elif len(groups) == 3:
                        # Quantity + unit price + total
                        quantity = float(groups[0])
                        unit_price = Decimal(groups[1])
                        total_price = Decimal(groups[2])
                        
                        # Validate calculation
                        if abs(unit_price * Decimal(str(quantity)) - total_price) < Decimal('0.02'):
                            description = f"Item (qty: {quantity})"
                            return ReceiptItem(
                                description=description,
                                quantity=quantity,
                                unit_price=unit_price,
                                total_price=total_price,
                                confidence=0.8
                            )
                
                except (ValueError, InvalidOperation):
                    continue
        
        return None
    
    def _is_valid_item_description(self, description: str) -> bool:
        """Check if description looks like a valid item."""
        # Filter out common non-item patterns
        invalid_patterns = [
            r'^\d+$',  # Just numbers
            r'^[A-Z]{1,2}$',  # Single/double letters
            r'total',
            r'subtotal',
            r'tax',
            r'cash',
            r'change',
            r'visa',
            r'mastercard',
            r'thank you',
            r'receipt',
            r'store.*\d+',
            r'^\*+$',  # Just asterisks
            r'^-+$',  # Just dashes
        ]
        
        description_lower = description.lower()
        
        for pattern in invalid_patterns:
            if re.search(pattern, description_lower):
                return False
        
        # Must have reasonable length
        if len(description) < 3 or len(description) > 50:
            return False
        
        # Should contain some letters
        if not re.search(r'[a-zA-Z]', description):
            return False
        
        return True
    
    def _deduplicate_items(self, items: List[ReceiptItem]) -> List[ReceiptItem]:
        """Remove duplicate items."""
        unique_items = []
        seen_descriptions = set()
        
        for item in items:
            description_key = item.description.lower().strip()
            if description_key not in seen_descriptions:
                seen_descriptions.add(description_key)
                unique_items.append(item)
        
        return unique_items
    
    def _validate_and_correct(self, receipt: ReceiptData) -> ReceiptData:
        """Validate and correct receipt data."""
        # Validate total calculations
        if receipt.subtotal and receipt.tax_amount and receipt.total_amount:
            calculated_total = receipt.subtotal + receipt.tax_amount
            if receipt.tip_amount:
                calculated_total += receipt.tip_amount
            
            # If totals don't match, prefer the explicit total
            if abs(calculated_total - receipt.total_amount) > Decimal('0.02'):
                self.logger.debug(f"Total mismatch: calculated {calculated_total}, receipt {receipt.total_amount}")
        
        # Validate item totals vs subtotal
        if receipt.items and receipt.subtotal:
            items_total = sum(item.total_price for item in receipt.items if item.total_price)
            if abs(items_total - receipt.subtotal) > Decimal('0.02'):
                self.logger.debug(f"Items total mismatch: {items_total} vs subtotal {receipt.subtotal}")
        
        # Validate date is reasonable
        if receipt.date:
            today = date.today()
            if receipt.date > today or (today - receipt.date).days > 365:
                self.logger.warning(f"Suspicious date: {receipt.date}")
        
        return receipt
    
    def _categorize_items(self, items: List[ReceiptItem]) -> None:
        """Add category information to items."""
        for item in items:
            category = self._determine_item_category(item.description)
            # Add category as a custom attribute (would need to extend ReceiptItem dataclass)
            # For now, we'll store it in a comment or modify the description
            if category:
                # Could extend ReceiptItem to include category field
                pass
    
    def _determine_item_category(self, description: str) -> Optional[str]:
        """Determine item category based on description."""
        description_lower = description.lower()
        
        for category, keywords in self.common_items.items():
            if any(keyword in description_lower for keyword in keywords):
                return category
        
        return None
    
    def _calculate_enhanced_confidence(self, receipt: ReceiptData) -> float:
        """Calculate enhanced confidence score."""
        confidence_factors = []
        
        # Base confidence from original extraction
        confidence_factors.append(receipt.confidence_score * 0.4)
        
        # Merchant identification bonus
        if receipt.merchant_name:
            confidence_factors.append(0.2)
        
        # Data completeness
        completeness = 0.0
        if receipt.date:
            completeness += 0.2
        if receipt.total_amount:
            completeness += 0.3
        if receipt.items:
            completeness += 0.3
        if receipt.tax_amount:
            completeness += 0.1
        if receipt.merchant_name:
            completeness += 0.1
        
        confidence_factors.append(completeness * 0.3)
        
        # Validation success
        validation_score = 0.5  # Base
        
        # Check if totals add up
        if (receipt.subtotal and receipt.tax_amount and receipt.total_amount and
            abs((receipt.subtotal + receipt.tax_amount) - receipt.total_amount) < Decimal('0.02')):
            validation_score += 0.3
        
        # Check if items total matches subtotal
        if receipt.items and receipt.subtotal:
            items_total = sum(item.total_price for item in receipt.items if item.total_price)
            if abs(items_total - receipt.subtotal) < Decimal('0.02'):
                validation_score += 0.2
        
        confidence_factors.append(min(validation_score, 1.0) * 0.1)
        
        return min(sum(confidence_factors), 1.0)