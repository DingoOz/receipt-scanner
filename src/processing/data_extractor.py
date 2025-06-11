import re
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation


@dataclass
class ReceiptItem:
    """Individual receipt item."""
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    confidence: float = 0.0


@dataclass
class ReceiptData:
    """Structured receipt data."""
    merchant_name: Optional[str] = None
    merchant_address: Optional[str] = None
    merchant_phone: Optional[str] = None
    
    date: Optional[date] = None
    time: Optional[str] = None
    
    items: List[ReceiptItem] = None
    
    subtotal: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    tip_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    
    payment_method: Optional[str] = None
    card_last_four: Optional[str] = None
    
    receipt_number: Optional[str] = None
    
    confidence_score: float = 0.0
    raw_text: str = ""
    
    def __post_init__(self):
        if self.items is None:
            self.items = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert Decimal to string for JSON serialization
        for key, value in result.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
        
        # Handle items list
        if result['items']:
            for item in result['items']:
                for item_key, item_value in item.items():
                    if isinstance(item_value, Decimal):
                        item[item_key] = str(item_value)
        
        # Convert date to string
        if result['date'] and hasattr(result['date'], 'isoformat'):
            result['date'] = result['date'].isoformat()
        
        return result


class ReceiptDataExtractor:
    """Extracts structured data from receipt text using regex patterns."""
    
    def __init__(self):
        """Initialize data extractor with regex patterns."""
        self.logger = logging.getLogger(__name__)
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile all regex patterns for better performance."""
        # Date patterns (various formats)
        self.date_patterns = [
            re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.IGNORECASE),
            re.compile(r'(\d{4}[/-]\d{1,2}[/-]\d{1,2})', re.IGNORECASE),
            re.compile(r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{2,4})', re.IGNORECASE),
            re.compile(r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{2,4})', re.IGNORECASE),
        ]
        
        # Time patterns
        self.time_patterns = [
            re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?)', re.IGNORECASE),
            re.compile(r'((?:1[0-2]|0?[1-9]):\d{2}\s*(?:am|pm))', re.IGNORECASE),
        ]
        
        # Amount patterns (currency)
        self.amount_patterns = [
            re.compile(r'\$?(\d+\.\d{2})', re.IGNORECASE),
            re.compile(r'(\d+,\d{3}\.\d{2})', re.IGNORECASE),
            re.compile(r'(\d+,\d{3},\d{3}\.\d{2})', re.IGNORECASE),
        ]
        
        # Total amount patterns
        self.total_patterns = [
            re.compile(r'(?:total|amount due|balance due|grand total)[:\s]*\$?(\d+\.\d{2})', re.IGNORECASE),
            re.compile(r'total[:\s]*(\d+\.\d{2})', re.IGNORECASE),
        ]
        
        # Subtotal patterns
        self.subtotal_patterns = [
            re.compile(r'(?:subtotal|sub total|sub-total)[:\s]*\$?(\d+\.\d{2})', re.IGNORECASE),
            re.compile(r'subtotal[:\s]*(\d+\.\d{2})', re.IGNORECASE),
        ]
        
        # Tax patterns
        self.tax_patterns = [
            re.compile(r'(?:tax|sales tax|vat)[:\s]*\$?(\d+\.\d{2})', re.IGNORECASE),
            re.compile(r'tax[:\s]*(\d+\.\d{2})', re.IGNORECASE),
        ]
        
        # Tip patterns
        self.tip_patterns = [
            re.compile(r'(?:tip|gratuity)[:\s]*\$?(\d+\.\d{2})', re.IGNORECASE),
        ]
        
        # Phone number patterns
        self.phone_patterns = [
            re.compile(r'(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})', re.IGNORECASE),
            re.compile(r'(\d{3}[-.\s]\d{3}[-.\s]\d{4})', re.IGNORECASE),
        ]
        
        # Receipt number patterns
        self.receipt_patterns = [
            re.compile(r'(?:receipt|ref|reference|order)[#\s:]*([a-z0-9]+)', re.IGNORECASE),
            re.compile(r'#([a-z0-9]{4,})', re.IGNORECASE),
        ]
        
        # Payment method patterns
        self.payment_patterns = [
            re.compile(r'(?:visa|mastercard|amex|american express|discover|cash|credit|debit)(?:\s+ending\s+in\s+(\d{4}))?', re.IGNORECASE),
        ]
        
        # Item line patterns (description + price)
        self.item_patterns = [
            re.compile(r'^(.+?)\s+\$?(\d+\.\d{2})$', re.MULTILINE),
            re.compile(r'^(\d+)\s+(.+?)\s+\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})$', re.MULTILINE),  # qty, desc, price, total
            re.compile(r'^(.+?)\s+(\d+)\s*x\s*\$?(\d+\.\d{2})\s+\$?(\d+\.\d{2})$', re.MULTILINE),  # desc, qty, price, total
        ]
    
    def extract_receipt_data(self, text: str, confidence: float = 0.0) -> ReceiptData:
        """
        Extract structured data from receipt text.
        
        Args:
            text: Raw OCR text from receipt
            confidence: OCR confidence score
            
        Returns:
            ReceiptData object with extracted information
        """
        try:
            receipt = ReceiptData(raw_text=text, confidence_score=confidence)
            
            # Clean and normalize text
            cleaned_text = self._clean_text(text)
            lines = cleaned_text.split('\n')
            
            # Extract merchant information (usually at the top)
            receipt.merchant_name = self._extract_merchant_name(lines[:5])
            receipt.merchant_address = self._extract_merchant_address(lines[:10])
            receipt.merchant_phone = self._extract_phone_number(text)
            
            # Extract date and time
            receipt.date = self._extract_date(text)
            receipt.time = self._extract_time(text)
            
            # Extract amounts
            receipt.total_amount = self._extract_total_amount(text)
            receipt.subtotal = self._extract_subtotal(text)
            receipt.tax_amount = self._extract_tax_amount(text)
            receipt.tip_amount = self._extract_tip_amount(text)
            
            # Extract payment information
            receipt.payment_method, receipt.card_last_four = self._extract_payment_method(text)
            receipt.receipt_number = self._extract_receipt_number(text)
            
            # Extract line items
            receipt.items = self._extract_items(text)
            
            # Calculate confidence score
            receipt.confidence_score = self._calculate_confidence_score(receipt, confidence)
            
            self.logger.debug(f"Extracted receipt data with confidence: {receipt.confidence_score:.2f}")
            return receipt
            
        except Exception as e:
            self.logger.error(f"Receipt data extraction failed: {str(e)}")
            return ReceiptData(raw_text=text, confidence_score=0.0)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for better parsing."""
        # Remove extra whitespace
        cleaned = re.sub(r'\s+', ' ', text)
        
        # Normalize currency symbols
        cleaned = re.sub(r'[$＄]', '$', cleaned)
        
        # Remove non-printable characters except newlines
        cleaned = re.sub(r'[^\x20-\x7E\n]', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_merchant_name(self, top_lines: List[str]) -> Optional[str]:
        """Extract merchant name from top lines of receipt."""
        for line in top_lines:
            line = line.strip()
            if len(line) > 3 and not self._is_address_line(line) and not self._is_phone_line(line):
                # Skip lines that are all caps and very short (likely headers)
                if len(line) > 8 or not line.isupper():
                    return line
        return None
    
    def _extract_merchant_address(self, top_lines: List[str]) -> Optional[str]:
        """Extract merchant address from receipt text."""
        address_parts = []
        for line in top_lines:
            line = line.strip()
            if self._is_address_line(line):
                address_parts.append(line)
        
        return ' '.join(address_parts) if address_parts else None
    
    def _is_address_line(self, line: str) -> bool:
        """Check if line looks like an address."""
        address_indicators = [
            r'\d+\s+\w+\s+(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|ct|court)',
            r'\w+,\s*[A-Z]{2}\s*\d{5}',  # City, State ZIP
            r'\d{3,5}\s+\w+',  # Street number + name
        ]
        
        for pattern in address_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False
    
    def _is_phone_line(self, line: str) -> bool:
        """Check if line contains a phone number."""
        return any(pattern.search(line) for pattern in self.phone_patterns)
    
    def _extract_phone_number(self, text: str) -> Optional[str]:
        """Extract phone number from text."""
        for pattern in self.phone_patterns:
            match = pattern.search(text)
            if match:
                return match.group(0).strip()
        return None
    
    def _extract_date(self, text: str) -> Optional[date]:
        """Extract date from receipt text."""
        for pattern in self.date_patterns:
            match = pattern.search(text)
            if match:
                date_str = match.group(1)
                try:
                    # Try various date formats
                    for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y/%m/%d', '%Y-%m-%d', 
                               '%m/%d/%y', '%m-%d-%y', '%B %d, %Y', '%b %d, %Y',
                               '%d %B %Y', '%d %b %Y']:
                        try:
                            return datetime.strptime(date_str, fmt).date()
                        except ValueError:
                            continue
                except Exception:
                    continue
        return None
    
    def _extract_time(self, text: str) -> Optional[str]:
        """Extract time from receipt text."""
        for pattern in self.time_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_amount(self, text: str, patterns: List[re.Pattern]) -> Optional[Decimal]:
        """Extract monetary amount using given patterns."""
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return Decimal(amount_str)
                except InvalidOperation:
                    continue
        return None
    
    def _extract_total_amount(self, text: str) -> Optional[Decimal]:
        """Extract total amount from receipt."""
        return self._extract_amount(text, self.total_patterns)
    
    def _extract_subtotal(self, text: str) -> Optional[Decimal]:
        """Extract subtotal from receipt."""
        return self._extract_amount(text, self.subtotal_patterns)
    
    def _extract_tax_amount(self, text: str) -> Optional[Decimal]:
        """Extract tax amount from receipt."""
        return self._extract_amount(text, self.tax_patterns)
    
    def _extract_tip_amount(self, text: str) -> Optional[Decimal]:
        """Extract tip amount from receipt."""
        return self._extract_amount(text, self.tip_patterns)
    
    def _extract_payment_method(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract payment method and card last four digits."""
        for pattern in self.payment_patterns:
            match = pattern.search(text)
            if match:
                payment_method = match.group(0).split()[0]
                last_four = match.group(1) if match.lastindex and match.lastindex >= 1 else None
                return payment_method, last_four
        return None, None
    
    def _extract_receipt_number(self, text: str) -> Optional[str]:
        """Extract receipt number from text."""
        for pattern in self.receipt_patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_items(self, text: str) -> List[ReceiptItem]:
        """Extract line items from receipt text."""
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue
            
            # Try different item patterns
            for pattern in self.item_patterns:
                match = pattern.match(line)
                if match:
                    item = self._parse_item_match(match)
                    if item:
                        items.append(item)
                    break
        
        return items
    
    def _parse_item_match(self, match: re.Match) -> Optional[ReceiptItem]:
        """Parse matched item line into ReceiptItem."""
        try:
            groups = match.groups()
            
            if len(groups) == 2:
                # Simple: description + price
                description = groups[0].strip()
                total_price = Decimal(groups[1])
                return ReceiptItem(description=description, total_price=total_price, confidence=0.8)
            
            elif len(groups) == 4:
                # Complex: qty + description + unit_price + total_price
                if groups[0].isdigit():
                    # qty, desc, unit_price, total
                    quantity = float(groups[0])
                    description = groups[1].strip()
                    unit_price = Decimal(groups[2])
                    total_price = Decimal(groups[3])
                else:
                    # desc, qty, unit_price, total
                    description = groups[0].strip()
                    quantity = float(groups[1])
                    unit_price = Decimal(groups[2])
                    total_price = Decimal(groups[3])
                
                return ReceiptItem(
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                    confidence=0.9
                )
            
        except (ValueError, InvalidOperation) as e:
            self.logger.debug(f"Failed to parse item match: {str(e)}")
        
        return None
    
    def _calculate_confidence_score(self, receipt: ReceiptData, ocr_confidence: float) -> float:
        """Calculate overall confidence score for extracted data."""
        confidence_factors = []
        
        # OCR confidence (40% weight)
        confidence_factors.append(ocr_confidence * 0.4)
        
        # Data completeness (30% weight)
        completeness_score = 0.0
        total_fields = 8
        
        if receipt.merchant_name:
            completeness_score += 1
        if receipt.date:
            completeness_score += 1
        if receipt.total_amount:
            completeness_score += 2  # Total is very important
        if receipt.subtotal:
            completeness_score += 1
        if receipt.tax_amount:
            completeness_score += 1
        if receipt.items:
            completeness_score += 1
        if receipt.payment_method:
            completeness_score += 1
        
        confidence_factors.append((completeness_score / total_fields) * 0.3)
        
        # Data consistency (20% weight)
        consistency_score = self._check_data_consistency(receipt)
        confidence_factors.append(consistency_score * 0.2)
        
        # Pattern recognition success (10% weight)
        pattern_score = 0.5  # Base score
        if receipt.merchant_name and len(receipt.merchant_name) > 3:
            pattern_score += 0.2
        if receipt.date:
            pattern_score += 0.2
        if receipt.total_amount:
            pattern_score += 0.1
        
        confidence_factors.append(min(pattern_score, 1.0) * 0.1)
        
        return sum(confidence_factors)
    
    def _check_data_consistency(self, receipt: ReceiptData) -> float:
        """Check consistency of extracted data."""
        consistency_score = 0.5  # Base score
        
        # Check if total matches subtotal + tax
        if receipt.total_amount and receipt.subtotal and receipt.tax_amount:
            calculated_total = receipt.subtotal + receipt.tax_amount
            if abs(calculated_total - receipt.total_amount) < Decimal('0.02'):
                consistency_score += 0.3
        
        # Check if items total matches subtotal
        if receipt.items and receipt.subtotal:
            items_total = sum(item.total_price for item in receipt.items if item.total_price)
            if abs(items_total - receipt.subtotal) < Decimal('0.02'):
                consistency_score += 0.2
        
        return min(consistency_score, 1.0)