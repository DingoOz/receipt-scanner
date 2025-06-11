import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from collections import defaultdict
import calendar

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from .data_formatter import DataFormatter, FormattingOptions


class ReportGenerator:
    """Generates visual reports and analytics from receipt data."""
    
    def __init__(self, output_dir: str = "output/reports"):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory for generated reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Set up matplotlib style
        plt.style.use('seaborn-v0_8' if 'seaborn-v0_8' in plt.style.available else 'default')
        sns.set_palette("husl")
    
    def generate_comprehensive_report(self, ocr_results: List[Dict[str, Any]], 
                                    source_name: str) -> Dict[str, Any]:
        """
        Generate a comprehensive PDF report with charts and statistics.
        
        Args:
            ocr_results: List of OCR processing results
            source_name: Name of the source (folder/album)
            
        Returns:
            Dict with report generation results
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_filename = f"receipt_report_{source_name}_{timestamp}.pdf"
            report_path = self.output_dir / report_filename
            
            # Filter valid receipts
            valid_receipts = [
                result for result in ocr_results 
                if result.get('success') and result.get('receipt_data')
            ]
            
            if not valid_receipts:
                return {
                    'success': False,
                    'error': 'No valid receipts to generate report',
                    'report_path': None
                }
            
            # Format data
            formatter = DataFormatter(FormattingOptions(show_confidence_scores=False))
            formatted_data = formatter.format_receipts_for_export(valid_receipts)
            receipts = formatted_data['formatted_receipts']
            summary = formatted_data['summary']
            
            # Generate report
            with PdfPages(report_path) as pdf:
                # Title page
                self._create_title_page(pdf, source_name, summary)
                
                # Executive summary
                self._create_executive_summary(pdf, receipts, summary)
                
                # Spending analysis
                self._create_spending_analysis(pdf, receipts)
                
                # Merchant analysis
                self._create_merchant_analysis(pdf, receipts)
                
                # Temporal analysis
                self._create_temporal_analysis(pdf, receipts)
                
                # Quality analysis
                self._create_quality_analysis(pdf, valid_receipts)
                
                # Detailed receipt list
                self._create_detailed_receipt_list(pdf, receipts)
            
            self.logger.info(f"Comprehensive report generated: {report_path}")
            
            return {
                'success': True,
                'report_path': str(report_path),
                'receipts_analyzed': len(valid_receipts),
                'pages_generated': 7,  # Approximate
                'file_size_mb': round(report_path.stat().st_size / (1024 * 1024), 2)
            }
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'report_path': None
            }
    
    def _create_title_page(self, pdf: PdfPages, source_name: str, summary: Dict[str, Any]):
        """Create title page."""
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        
        # Title
        ax.text(0.5, 0.8, 'Receipt Analysis Report', 
                ha='center', va='center', fontsize=24, fontweight='bold')
        
        # Source info
        ax.text(0.5, 0.7, f'Source: {source_name}', 
                ha='center', va='center', fontsize=16)
        
        # Date
        ax.text(0.5, 0.65, f'Generated: {datetime.now().strftime("%B %d, %Y")}', 
                ha='center', va='center', fontsize=14)
        
        # Key statistics
        stats_text = f"""
Key Statistics:
• Total Receipts: {summary['totals']['receipts_count']}
• Total Amount: {summary['totals']['amount']}
• Unique Merchants: {summary['totals']['unique_merchants']}
• Date Range: {summary['date_range']['earliest']} to {summary['date_range']['latest']}
"""
        
        ax.text(0.5, 0.4, stats_text, 
                ha='center', va='center', fontsize=12,
                bbox=dict(boxstyle="round,pad=0.5", facecolor="lightblue", alpha=0.7))
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_executive_summary(self, pdf: PdfPages, receipts: List[Dict[str, Any]], 
                                summary: Dict[str, Any]):
        """Create executive summary page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(8.5, 11))
        fig.suptitle('Executive Summary', fontsize=16, fontweight='bold')
        
        # Total spending over time
        dates = []
        amounts = []
        for receipt in receipts:
            if receipt['transaction']['date'] and receipt['amounts']['total']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    dates.append(date_obj)
                    amounts.append(amount)
                except:
                    continue
        
        if dates and amounts:
            # Cumulative spending
            sorted_data = sorted(zip(dates, amounts))
            cum_dates, cum_amounts = zip(*sorted_data)
            cumulative = [sum(cum_amounts[:i+1]) for i in range(len(cum_amounts))]
            
            ax1.plot(cum_dates, cumulative, marker='o', linewidth=2)
            ax1.set_title('Cumulative Spending')
            ax1.set_ylabel('Amount ($)')
            ax1.tick_params(axis='x', rotation=45)
            
            # Daily spending
            ax2.bar(cum_dates, cum_amounts, alpha=0.7)
            ax2.set_title('Daily Spending')
            ax2.set_ylabel('Amount ($)')
            ax2.tick_params(axis='x', rotation=45)
        
        # Top merchants by spending
        merchant_totals = defaultdict(float)
        for receipt in receipts:
            merchant = receipt['merchant']['name'] or 'Unknown'
            if receipt['amounts']['total']:
                try:
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    merchant_totals[merchant] += amount
                except:
                    continue
        
        if merchant_totals:
            top_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:10]
            merchants, amounts = zip(*top_merchants)
            
            ax3.barh(merchants, amounts)
            ax3.set_title('Top Merchants by Spending')
            ax3.set_xlabel('Amount ($)')
        
        # Spending distribution
        all_amounts = [float(receipt['amounts']['total'].replace('$', '').replace(',', '')) 
                      for receipt in receipts 
                      if receipt['amounts']['total']]
        
        if all_amounts:
            ax4.hist(all_amounts, bins=20, alpha=0.7, edgecolor='black')
            ax4.set_title('Spending Distribution')
            ax4.set_xlabel('Amount ($)')
            ax4.set_ylabel('Frequency')
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_spending_analysis(self, pdf: PdfPages, receipts: List[Dict[str, Any]]):
        """Create spending analysis page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(8.5, 11))
        fig.suptitle('Spending Analysis', fontsize=16, fontweight='bold')
        
        # Monthly spending
        monthly_spending = defaultdict(float)
        for receipt in receipts:
            if receipt['transaction']['date'] and receipt['amounts']['total']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    month_key = date_obj.strftime('%Y-%m')
                    monthly_spending[month_key] += amount
                except:
                    continue
        
        if monthly_spending:
            months = sorted(monthly_spending.keys())
            amounts = [monthly_spending[month] for month in months]
            
            ax1.bar(months, amounts, alpha=0.7)
            ax1.set_title('Monthly Spending')
            ax1.set_ylabel('Amount ($)')
            ax1.tick_params(axis='x', rotation=45)
        
        # Day of week spending
        dow_spending = defaultdict(list)
        for receipt in receipts:
            if receipt['transaction']['date'] and receipt['amounts']['total']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    dow = date_obj.strftime('%A')
                    dow_spending[dow].append(amount)
                except:
                    continue
        
        if dow_spending:
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            avg_amounts = [sum(dow_spending[day])/len(dow_spending[day]) if dow_spending[day] else 0 
                          for day in days]
            
            ax2.bar(days, avg_amounts, alpha=0.7)
            ax2.set_title('Average Spending by Day of Week')
            ax2.set_ylabel('Average Amount ($)')
            ax2.tick_params(axis='x', rotation=45)
        
        # Payment method distribution
        payment_methods = defaultdict(int)
        for receipt in receipts:
            method = receipt['payment']['method'] or 'Unknown'
            payment_methods[method] += 1
        
        if payment_methods:
            methods, counts = zip(*payment_methods.items())
            ax3.pie(counts, labels=methods, autopct='%1.1f%%', startangle=90)
            ax3.set_title('Payment Methods')
        
        # Tax analysis
        tax_amounts = []
        total_amounts = []
        for receipt in receipts:
            if receipt['amounts']['tax'] and receipt['amounts']['total']:
                try:
                    tax = float(receipt['amounts']['tax'].replace('$', '').replace(',', ''))
                    total = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    if total > 0:
                        tax_rate = (tax / total) * 100
                        if 0 <= tax_rate <= 20:  # Reasonable tax rate range
                            tax_amounts.append(tax_rate)
                except:
                    continue
        
        if tax_amounts:
            ax4.hist(tax_amounts, bins=15, alpha=0.7, edgecolor='black')
            ax4.set_title('Tax Rate Distribution')
            ax4.set_xlabel('Tax Rate (%)')
            ax4.set_ylabel('Frequency')
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_merchant_analysis(self, pdf: PdfPages, receipts: List[Dict[str, Any]]):
        """Create merchant analysis page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(8.5, 11))
        fig.suptitle('Merchant Analysis', fontsize=16, fontweight='bold')
        
        # Merchant frequency
        merchant_counts = defaultdict(int)
        merchant_totals = defaultdict(float)
        
        for receipt in receipts:
            merchant = receipt['merchant']['name'] or 'Unknown'
            merchant_counts[merchant] += 1
            
            if receipt['amounts']['total']:
                try:
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    merchant_totals[merchant] += amount
                except:
                    continue
        
        # Top merchants by frequency
        if merchant_counts:
            top_by_freq = sorted(merchant_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            merchants, counts = zip(*top_by_freq)
            
            ax1.barh(merchants, counts)
            ax1.set_title('Top Merchants by Visits')
            ax1.set_xlabel('Number of Visits')
        
        # Top merchants by spending
        if merchant_totals:
            top_by_amount = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:10]
            merchants, amounts = zip(*top_by_amount)
            
            ax2.barh(merchants, amounts)
            ax2.set_title('Top Merchants by Spending')
            ax2.set_xlabel('Total Amount ($)')
        
        # Average spending per merchant
        avg_spending = {}
        for merchant in merchant_counts:
            if merchant_counts[merchant] > 0:
                avg_spending[merchant] = merchant_totals[merchant] / merchant_counts[merchant]
        
        if avg_spending:
            top_avg = sorted(avg_spending.items(), key=lambda x: x[1], reverse=True)[:10]
            merchants, averages = zip(*top_avg)
            
            ax3.barh(merchants, averages)
            ax3.set_title('Highest Average Spending per Visit')
            ax3.set_xlabel('Average Amount ($)')
        
        # Merchant spending distribution (pie chart)
        if merchant_totals:
            # Group smaller merchants into "Others"
            top_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:8]
            others_total = sum(amount for merchant, amount in merchant_totals.items() 
                             if merchant not in [m for m, a in top_merchants])
            
            if others_total > 0:
                top_merchants.append(('Others', others_total))
            
            merchants, amounts = zip(*top_merchants)
            ax4.pie(amounts, labels=merchants, autopct='%1.1f%%', startangle=90)
            ax4.set_title('Spending Distribution by Merchant')
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_temporal_analysis(self, pdf: PdfPages, receipts: List[Dict[str, Any]]):
        """Create temporal analysis page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(8.5, 11))
        fig.suptitle('Temporal Analysis', fontsize=16, fontweight='bold')
        
        # Time of day analysis (if time data available)
        hour_spending = defaultdict(list)
        for receipt in receipts:
            if receipt['transaction']['time'] and receipt['amounts']['total']:
                try:
                    time_str = receipt['transaction']['time']
                    hour = int(time_str.split(':')[0])
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    hour_spending[hour].append(amount)
                except:
                    continue
        
        if hour_spending:
            hours = sorted(hour_spending.keys())
            avg_amounts = [sum(hour_spending[hour])/len(hour_spending[hour]) for hour in hours]
            
            ax1.bar(hours, avg_amounts, alpha=0.7)
            ax1.set_title('Average Spending by Hour of Day')
            ax1.set_xlabel('Hour (24-hour format)')
            ax1.set_ylabel('Average Amount ($)')
        
        # Weekly pattern
        week_spending = defaultdict(float)
        for receipt in receipts:
            if receipt['transaction']['date'] and receipt['amounts']['total']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    
                    # Get week number
                    week_num = date_obj.isocalendar()[1]
                    week_key = f"{date_obj.year}-W{week_num:02d}"
                    week_spending[week_key] += amount
                except:
                    continue
        
        if week_spending:
            weeks = sorted(week_spending.keys())[-12:]  # Last 12 weeks
            amounts = [week_spending[week] for week in weeks]
            
            ax2.plot(weeks, amounts, marker='o', linewidth=2)
            ax2.set_title('Weekly Spending Trend')
            ax2.set_ylabel('Amount ($)')
            ax2.tick_params(axis='x', rotation=45)
        
        # Seasonal analysis
        seasonal_spending = defaultdict(float)
        for receipt in receipts:
            if receipt['transaction']['date'] and receipt['amounts']['total']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    amount = float(receipt['amounts']['total'].replace('$', '').replace(',', ''))
                    
                    # Determine season
                    month = date_obj.month
                    if month in [12, 1, 2]:
                        season = 'Winter'
                    elif month in [3, 4, 5]:
                        season = 'Spring'
                    elif month in [6, 7, 8]:
                        season = 'Summer'
                    else:
                        season = 'Fall'
                    
                    seasonal_spending[season] += amount
                except:
                    continue
        
        if seasonal_spending:
            seasons = ['Spring', 'Summer', 'Fall', 'Winter']
            amounts = [seasonal_spending[season] for season in seasons]
            
            ax3.bar(seasons, amounts, alpha=0.7)
            ax3.set_title('Seasonal Spending')
            ax3.set_ylabel('Total Amount ($)')
        
        # Receipt frequency over time
        daily_counts = defaultdict(int)
        for receipt in receipts:
            if receipt['transaction']['date']:
                try:
                    date_obj = datetime.strptime(receipt['transaction']['date'], '%Y-%m-%d').date()
                    daily_counts[date_obj] += 1
                except:
                    continue
        
        if daily_counts:
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[date] for date in dates]
            
            ax4.plot(dates, counts, marker='o', linewidth=2, alpha=0.7)
            ax4.set_title('Receipt Frequency Over Time')
            ax4.set_ylabel('Number of Receipts')
            ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_quality_analysis(self, pdf: PdfPages, ocr_results: List[Dict[str, Any]]):
        """Create OCR quality analysis page."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(8.5, 11))
        fig.suptitle('OCR Quality Analysis', fontsize=16, fontweight='bold')
        
        # OCR confidence distribution
        ocr_confidences = [result.get('ocr_confidence', 0) for result in ocr_results]
        
        if ocr_confidences:
            ax1.hist([c * 100 for c in ocr_confidences], bins=20, alpha=0.7, edgecolor='black')
            ax1.set_title('OCR Confidence Distribution')
            ax1.set_xlabel('OCR Confidence (%)')
            ax1.set_ylabel('Frequency')
        
        # Validation confidence distribution
        validation_confidences = [
            result['receipt_data'].get('confidence_score', 0) 
            for result in ocr_results 
            if result.get('receipt_data')
        ]
        
        if validation_confidences:
            ax2.hist([c * 100 for c in validation_confidences], bins=20, alpha=0.7, edgecolor='black')
            ax2.set_title('Validation Confidence Distribution')
            ax2.set_xlabel('Validation Confidence (%)')
            ax2.set_ylabel('Frequency')
        
        # OCR method usage
        ocr_methods = defaultdict(int)
        for result in ocr_results:
            method = result.get('ocr_method', 'unknown')
            ocr_methods[method] += 1
        
        if ocr_methods:
            methods, counts = zip(*ocr_methods.items())
            ax3.pie(counts, labels=methods, autopct='%1.1f%%', startangle=90)
            ax3.set_title('OCR Methods Used')
        
        # Processing time analysis
        processing_times = [
            result.get('processing_time', 0) 
            for result in ocr_results 
            if result.get('processing_time', 0) > 0
        ]
        
        if processing_times:
            ax4.hist(processing_times, bins=20, alpha=0.7, edgecolor='black')
            ax4.set_title('Processing Time Distribution')
            ax4.set_xlabel('Processing Time (seconds)')
            ax4.set_ylabel('Frequency')
        
        plt.tight_layout()
        pdf.savefig(fig)
        plt.close()
    
    def _create_detailed_receipt_list(self, pdf: PdfPages, receipts: List[Dict[str, Any]]):
        """Create detailed receipt list page."""
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        
        ax.text(0.5, 0.95, 'Detailed Receipt List', 
                ha='center', va='top', fontsize=16, fontweight='bold')
        
        # Create table data
        table_data = []
        headers = ['Date', 'Merchant', 'Amount', 'Items', 'Confidence']
        
        for receipt in receipts[:25]:  # Limit to first 25 receipts
            row = [
                receipt['transaction']['date'] or 'Unknown',
                (receipt['merchant']['name'] or 'Unknown')[:20],  # Truncate long names
                receipt['amounts']['total'] or '$0.00',
                str(receipt['metadata']['items_count']),
                f"{float(receipt.get('confidence', {}).get('validation_confidence', '0%').replace('%', '')):.0f}%" 
                if receipt.get('confidence', {}).get('validation_confidence') else 'N/A'
            ]
            table_data.append(row)
        
        # Create table
        if table_data:
            table = ax.table(cellText=table_data, colLabels=headers, 
                           cellLoc='center', loc='center',
                           bbox=[0.1, 0.1, 0.8, 0.8])
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.5)
            
            # Style header row
            for i in range(len(headers)):
                table[(0, i)].set_facecolor('#40466e')
                table[(0, i)].set_text_props(weight='bold', color='white')
        
        if len(receipts) > 25:
            ax.text(0.5, 0.05, f'Showing first 25 of {len(receipts)} receipts', 
                    ha='center', va='bottom', fontsize=10, style='italic')
        
        pdf.savefig(fig)
        plt.close()
    
    def generate_quick_summary_chart(self, ocr_results: List[Dict[str, Any]], 
                                   chart_type: str = 'spending_by_merchant') -> str:
        """
        Generate a quick summary chart.
        
        Args:
            ocr_results: List of OCR processing results
            chart_type: Type of chart to generate
            
        Returns:
            Path to generated chart image
        """
        try:
            valid_receipts = [
                result for result in ocr_results 
                if result.get('success') and result.get('receipt_data')
            ]
            
            if not valid_receipts:
                raise ValueError("No valid receipts to chart")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            chart_path = self.output_dir / f"chart_{chart_type}_{timestamp}.png"
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            if chart_type == 'spending_by_merchant':
                self._create_spending_by_merchant_chart(ax, valid_receipts)
            elif chart_type == 'spending_over_time':
                self._create_spending_over_time_chart(ax, valid_receipts)
            elif chart_type == 'payment_methods':
                self._create_payment_methods_chart(ax, valid_receipts)
            else:
                raise ValueError(f"Unknown chart type: {chart_type}")
            
            plt.tight_layout()
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Chart generated: {chart_path}")
            return str(chart_path)
            
        except Exception as e:
            self.logger.error(f"Chart generation failed: {str(e)}")
            raise
    
    def _create_spending_by_merchant_chart(self, ax, receipts):
        """Create spending by merchant chart."""
        merchant_totals = defaultdict(float)
        
        for receipt in receipts:
            merchant = receipt['receipt_data'].get('merchant_name', 'Unknown')
            amount_str = receipt['receipt_data'].get('total_amount', '0')
            try:
                amount = float(str(amount_str).replace('$', '').replace(',', ''))
                merchant_totals[merchant] += amount
            except:
                continue
        
        if merchant_totals:
            sorted_merchants = sorted(merchant_totals.items(), key=lambda x: x[1], reverse=True)[:10]
            merchants, amounts = zip(*sorted_merchants)
            
            bars = ax.barh(merchants, amounts)
            ax.set_xlabel('Total Amount ($)')
            ax.set_title('Top 10 Merchants by Spending')
            
            # Add value labels on bars
            for bar, amount in zip(bars, amounts):
                ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2, 
                       f'${amount:.2f}', ha='left', va='center')
    
    def _create_spending_over_time_chart(self, ax, receipts):
        """Create spending over time chart."""
        daily_totals = defaultdict(float)
        
        for receipt in receipts:
            date_str = receipt['receipt_data'].get('date')
            amount_str = receipt['receipt_data'].get('total_amount', '0')
            
            if date_str:
                try:
                    amount = float(str(amount_str).replace('$', '').replace(',', ''))
                    daily_totals[date_str] += amount
                except:
                    continue
        
        if daily_totals:
            dates = sorted(daily_totals.keys())
            amounts = [daily_totals[date] for date in dates]
            
            ax.plot(dates, amounts, marker='o', linewidth=2)
            ax.set_ylabel('Amount ($)')
            ax.set_title('Spending Over Time')
            ax.tick_params(axis='x', rotation=45)
    
    def _create_payment_methods_chart(self, ax, receipts):
        """Create payment methods chart."""
        payment_counts = defaultdict(int)
        
        for receipt in receipts:
            method = receipt['receipt_data'].get('payment_method', 'Unknown')
            payment_counts[method] += 1
        
        if payment_counts:
            methods, counts = zip(*payment_counts.items())
            
            ax.pie(counts, labels=methods, autopct='%1.1f%%', startangle=90)
            ax.set_title('Payment Methods Distribution')