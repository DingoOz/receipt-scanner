import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
from datetime import date, datetime

from .data_extractor import ReceiptData, ReceiptItem


class ReceiptValidator:
    """Validates and scores receipt data quality and confidence."""
    
    def __init__(self, min_confidence_threshold: float = 0.6):
        """
        Initialize validator.
        
        Args:
            min_confidence_threshold: Minimum confidence for valid receipts
        """
        self.min_confidence_threshold = min_confidence_threshold
        self.logger = logging.getLogger(__name__)
    
    def validate_receipt(self, receipt: ReceiptData) -> Dict[str, Any]:
        """
        Comprehensive validation of receipt data.
        
        Args:
            receipt: Receipt data to validate
            
        Returns:
            Dict with validation results and scores
        """
        validation_result = {
            'is_valid': False,
            'confidence_score': 0.0,
            'validation_scores': {},
            'issues': [],
            'warnings': [],
            'suggestions': []
        }
        
        try:
            # Individual validation checks
            validation_result['validation_scores']['merchant'] = self._validate_merchant_info(receipt, validation_result)
            validation_result['validation_scores']['date_time'] = self._validate_date_time(receipt, validation_result)
            validation_result['validation_scores']['amounts'] = self._validate_amounts(receipt, validation_result)
            validation_result['validation_scores']['items'] = self._validate_items(receipt, validation_result)
            validation_result['validation_scores']['calculations'] = self._validate_calculations(receipt, validation_result)
            validation_result['validation_scores']['data_quality'] = self._validate_data_quality(receipt, validation_result)
            
            # Calculate overall confidence score
            overall_confidence = self._calculate_overall_confidence(validation_result['validation_scores'], receipt)
            validation_result['confidence_score'] = overall_confidence
            
            # Determine if receipt is valid
            validation_result['is_valid'] = (
                overall_confidence >= self.min_confidence_threshold and
                len([issue for issue in validation_result['issues'] if issue['severity'] == 'critical']) == 0
            )
            
            self.logger.debug(f"Receipt validation: {overall_confidence:.2f} confidence, {'valid' if validation_result['is_valid'] else 'invalid'}")
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Receipt validation failed: {str(e)}")
            validation_result['issues'].append({
                'type': 'validation_error',
                'severity': 'critical',
                'message': f"Validation process failed: {str(e)}"
            })
            return validation_result
    
    def _validate_merchant_info(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate merchant information."""
        score = 0.0
        
        # Merchant name
        if receipt.merchant_name:
            if len(receipt.merchant_name.strip()) >= 3:
                score += 0.5
                if self._is_reasonable_merchant_name(receipt.merchant_name):
                    score += 0.3
            else:
                result['issues'].append({
                    'type': 'merchant_name_too_short',
                    'severity': 'warning',
                    'message': 'Merchant name is too short'
                })
        else:
            result['issues'].append({
                'type': 'missing_merchant_name',
                'severity': 'minor',
                'message': 'Merchant name not found'
            })
        
        # Merchant address
        if receipt.merchant_address:
            if len(receipt.merchant_address.strip()) >= 10:
                score += 0.1
        
        # Merchant phone
        if receipt.merchant_phone:
            if self._is_valid_phone_format(receipt.merchant_phone):
                score += 0.1
        
        return min(score, 1.0)
    
    def _validate_date_time(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate date and time information."""
        score = 0.0
        
        # Date validation
        if receipt.date:
            if self._is_reasonable_date(receipt.date):
                score += 0.7
            else:
                result['issues'].append({
                    'type': 'unreasonable_date',
                    'severity': 'warning',
                    'message': f'Date seems unreasonable: {receipt.date}'
                })
                score += 0.3  # Partial credit
        else:
            result['issues'].append({
                'type': 'missing_date',
                'severity': 'minor',
                'message': 'Receipt date not found'
            })
        
        # Time validation
        if receipt.time:
            if self._is_valid_time_format(receipt.time):
                score += 0.3
            else:
                result['warnings'].append({
                    'type': 'invalid_time_format',
                    'message': f'Time format seems invalid: {receipt.time}'
                })
        
        return min(score, 1.0)
    
    def _validate_amounts(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate monetary amounts."""
        score = 0.0
        
        # Total amount (most important)
        if receipt.total_amount:
            if self._is_reasonable_amount(receipt.total_amount):
                score += 0.5
            else:
                result['issues'].append({
                    'type': 'unreasonable_total',
                    'severity': 'warning',
                    'message': f'Total amount seems unreasonable: ${receipt.total_amount}'
                })
        else:
            result['issues'].append({
                'type': 'missing_total',
                'severity': 'critical',
                'message': 'Total amount not found'
            })
        
        # Subtotal
        if receipt.subtotal:
            if self._is_reasonable_amount(receipt.subtotal):
                score += 0.2
        
        # Tax amount
        if receipt.tax_amount:
            if self._is_reasonable_amount(receipt.tax_amount):
                score += 0.1
                # Tax should be reasonable percentage of subtotal
                if receipt.subtotal:
                    tax_rate = receipt.tax_amount / receipt.subtotal
                    if 0.01 <= tax_rate <= 0.20:  # 1% to 20% tax rate
                        score += 0.1
                    else:
                        result['warnings'].append({
                            'type': 'unusual_tax_rate',
                            'message': f'Tax rate seems unusual: {tax_rate*100:.1f}%'
                        })
        
        # Tip amount (if present)
        if receipt.tip_amount:
            if self._is_reasonable_amount(receipt.tip_amount):
                score += 0.1
        
        return min(score, 1.0)
    
    def _validate_items(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate line items."""
        score = 0.0
        
        if not receipt.items:
            result['issues'].append({
                'type': 'no_items',
                'severity': 'minor',
                'message': 'No line items found'
            })
            return 0.0
        
        valid_items = 0
        total_items = len(receipt.items)
        
        for item in receipt.items:
            item_score = 0.0
            
            # Description
            if item.description and len(item.description.strip()) >= 3:
                item_score += 0.5
            
            # Price
            if item.total_price and self._is_reasonable_amount(item.total_price):
                item_score += 0.3
            
            # Quantity and unit price consistency
            if item.quantity and item.unit_price and item.total_price:
                calculated_total = item.unit_price * Decimal(str(item.quantity))
                if abs(calculated_total - item.total_price) < Decimal('0.02'):
                    item_score += 0.2
                else:
                    result['warnings'].append({
                        'type': 'item_calculation_mismatch',
                        'message': f'Item calculation mismatch: {item.description}'
                    })
            
            if item_score >= 0.5:
                valid_items += 1
        
        # Score based on percentage of valid items
        if total_items > 0:
            score = valid_items / total_items
        
        return score
    
    def _validate_calculations(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate mathematical calculations."""
        score = 0.5  # Base score
        
        # Check subtotal + tax = total
        if receipt.subtotal and receipt.tax_amount and receipt.total_amount:
            calculated_total = receipt.subtotal + receipt.tax_amount
            if receipt.tip_amount:
                calculated_total += receipt.tip_amount
            
            if abs(calculated_total - receipt.total_amount) < Decimal('0.02'):
                score += 0.3
            else:
                result['issues'].append({
                    'type': 'total_calculation_error',
                    'severity': 'warning',
                    'message': f'Total calculation mismatch: {calculated_total} vs {receipt.total_amount}'
                })
        
        # Check items total = subtotal
        if receipt.items and receipt.subtotal:
            items_total = sum(item.total_price for item in receipt.items if item.total_price)
            if abs(items_total - receipt.subtotal) < Decimal('0.05'):  # Allow slightly more tolerance
                score += 0.2
            else:
                result['warnings'].append({
                    'type': 'items_subtotal_mismatch',
                    'message': f'Items total ({items_total}) != subtotal ({receipt.subtotal})'
                })
        
        return min(score, 1.0)
    
    def _validate_data_quality(self, receipt: ReceiptData, result: Dict[str, Any]) -> float:
        """Validate overall data quality."""
        score = 0.0
        
        # OCR confidence
        if receipt.confidence_score:
            score += receipt.confidence_score * 0.4
        
        # Data completeness
        completeness_fields = [
            receipt.merchant_name,
            receipt.date,
            receipt.total_amount,
            receipt.subtotal,
            receipt.tax_amount,
            receipt.items,
            receipt.payment_method
        ]
        
        completeness_score = sum(1 for field in completeness_fields if field) / len(completeness_fields)
        score += completeness_score * 0.3
        
        # Raw text quality
        if receipt.raw_text:
            text_quality = self._assess_text_quality(receipt.raw_text)
            score += text_quality * 0.3
        
        return min(score, 1.0)
    
    def _is_reasonable_merchant_name(self, name: str) -> bool:
        """Check if merchant name seems reasonable."""
        name = name.strip().lower()
        
        # Filter out common OCR artifacts
        invalid_patterns = [
            r'^[0-9\*\-\+\=]+$',  # Just numbers/symbols
            r'^[a-z]{1,2}$',      # Too short
            r'^(total|subtotal|tax|cash)$',  # Common receipt words
            r'^\*+$',             # Just asterisks
        ]
        
        import re
        for pattern in invalid_patterns:
            if re.match(pattern, name):
                return False
        
        return 3 <= len(name) <= 50
    
    def _is_reasonable_date(self, receipt_date: date) -> bool:
        """Check if date is reasonable."""
        today = date.today()
        
        # Date should not be in the future
        if receipt_date > today:
            return False
        
        # Date should not be more than 10 years old
        days_old = (today - receipt_date).days
        if days_old > 3650:  # 10 years
            return False
        
        return True
    
    def _is_valid_time_format(self, time_str: str) -> bool:
        """Check if time format is valid."""
        import re
        time_patterns = [
            r'^\d{1,2}:\d{2}$',           # HH:MM
            r'^\d{1,2}:\d{2}:\d{2}$',     # HH:MM:SS
            r'^\d{1,2}:\d{2}\s*(am|pm)$', # HH:MM AM/PM
        ]
        
        for pattern in time_patterns:
            if re.match(pattern, time_str.lower()):
                return True
        
        return False
    
    def _is_valid_phone_format(self, phone: str) -> bool:
        """Check if phone number format is valid."""
        import re
        phone_patterns = [
            r'^\d{3}-\d{3}-\d{4}$',
            r'^\(\d{3}\)\s*\d{3}-\d{4}$',
            r'^\d{3}\.\d{3}\.\d{4}$',
            r'^\d{10}$'
        ]
        
        for pattern in phone_patterns:
            if re.match(pattern, phone):
                return True
        
        return False
    
    def _is_reasonable_amount(self, amount: Decimal) -> bool:
        """Check if monetary amount is reasonable."""
        # Amount should be positive
        if amount <= 0:
            return False
        
        # Amount should not be extremely large (> $10,000)
        if amount > Decimal('10000.00'):
            return False
        
        # Amount should have reasonable precision (max 2 decimal places)
        if amount.as_tuple().exponent < -2:
            return False
        
        return True
    
    def _assess_text_quality(self, text: str) -> float:
        """Assess quality of raw OCR text."""
        if not text:
            return 0.0
        
        score = 0.0
        
        # Length check
        if len(text) > 50:
            score += 0.3
        elif len(text) > 20:
            score += 0.2
        
        # Character variety
        has_letters = any(c.isalpha() for c in text)
        has_numbers = any(c.isdigit() for c in text)
        has_punctuation = any(c in '.,;:!?$()[]{}' for c in text)
        
        if has_letters:
            score += 0.3
        if has_numbers:
            score += 0.2
        if has_punctuation:
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_overall_confidence(self, validation_scores: Dict[str, float], receipt: ReceiptData) -> float:
        """Calculate overall confidence score from individual validation scores."""
        # Weighted average of validation scores
        weights = {
            'amounts': 0.3,      # Most important
            'calculations': 0.25, # Very important for accuracy
            'merchant': 0.15,
            'items': 0.15,
            'date_time': 0.1,
            'data_quality': 0.05
        }
        
        weighted_score = 0.0
        total_weight = 0.0
        
        for category, weight in weights.items():
            if category in validation_scores:
                weighted_score += validation_scores[category] * weight
                total_weight += weight
        
        # Normalize
        if total_weight > 0:
            return weighted_score / total_weight
        else:
            return 0.0
    
    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """Generate human-readable validation summary."""
        summary_parts = []
        
        summary_parts.append(f"Overall Confidence: {validation_result['confidence_score']:.1%}")
        summary_parts.append(f"Status: {'Valid' if validation_result['is_valid'] else 'Invalid'}")
        
        if validation_result['issues']:
            critical_issues = [i for i in validation_result['issues'] if i['severity'] == 'critical']
            warning_issues = [i for i in validation_result['issues'] if i['severity'] == 'warning']
            minor_issues = [i for i in validation_result['issues'] if i['severity'] == 'minor']
            
            if critical_issues:
                summary_parts.append(f"Critical Issues: {len(critical_issues)}")
            if warning_issues:
                summary_parts.append(f"Warnings: {len(warning_issues)}")
            if minor_issues:
                summary_parts.append(f"Minor Issues: {len(minor_issues)}")
        
        # Score breakdown
        scores = validation_result['validation_scores']
        if scores:
            summary_parts.append("Score Breakdown:")
            for category, score in scores.items():
                summary_parts.append(f"  {category.title()}: {score:.1%}")
        
        return "\n".join(summary_parts)