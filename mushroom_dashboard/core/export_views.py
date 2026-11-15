"""Admin "Export PDF" and "Convert to CSV" endpoints.

Each page that exports has a *_pdf and *_csv view. Analytics is PDF-only.
Layout/formatting lives in core/exports.py so every export looks the same.
"""
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from . import exports as ex
from .models import Order, OrderItem, Product, ProductionBatch, Sale, SensorReading
from .views import admin_required, analytics_api, calculate_growth_days

SALES_STATUSES = ['DELIVERED', 'PROCESSING', 'SHIPPED', 'PAID']
LOW_STOCK_LIMIT = 10
PDF_ROW_CAP = 1500  # keeps very long histories from producing huge PDFs


def _parse_date(value, default):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date() if value else default
    except ValueError:
        return default


def _date_range(request):
    today = timezone.localdate()
    end = _parse_date(request.GET.get('end_date'), today)
    start = _parse_date(request.GET.get('start_date'), today - timedelta(days=30))
    if start > end:
        start, end = end, start
    return start, end


def _stock_status(product):
    if product.stock_kg <= 0:
        return 'Out of Stock'
    return 'Low Stock' if product.stock_kg < LOW_STOCK_LIMIT else 'In Stock'


def _capped(rows):
    """Return (rows_for_pdf, note) so long tables stay readable."""
    rows = list(rows)
    if len(rows) > PDF_ROW_CAP:
        return rows[:PDF_ROW_CAP], f'Showing the latest {PDF_ROW_CAP:,} of {len(rows):,} records. Use Convert to CSV for the full list.'
    return rows, None


# ==========================================================================
# Sales report
# ==========================================================================
def _sales_orders(request):
    start, end = _date_range(request)
    orders = Order.objects.filter(
        created_at__date__gte=start,
        created_at__date__lte=end,
        status__in=SALES_STATUSES,
    ).order_by('-created_at')
    return start, end, orders


@admin_required
def sales_report_export(request):
    start, end, orders = _sales_orders(request)
    order_list = list(orders)
    total_sales = sum((o.total_amount for o in order_list), Decimal('0'))
    total_orders = len(order_list)
    average = total_sales / total_orders if total_orders else Decimal('0')

    by_payment = {}
    for o in order_list:
        key = 'GCash' if o.payment_method == 'GCASH' else 'Cash on Delivery'
        entry = by_payment.setdefault(key, [0, Decimal('0')])
        entry[0] += 1
        entry[1] += o.total_amount

    best = OrderItem.objects.filter(
        order__created_at__date__gte=start, order__created_at__date__lte=end,
        order__status__in=SALES_STATUSES,
    ).values('product__name').annotate(qty=Sum('quantity_kg'), revenue=Sum('subtotal')).order_by('-revenue')[:10]

    pdf_orders, note = _capped(order_list)
    sections = [
        {
            'heading': 'Sales by Payment Method',
            'headers': ['Payment Method', 'Orders', 'Total Sales'],
            'rows': [[k, v[0], ex.money(v[1])] for k, v in by_payment.items()],
            'widths': [3, 1, 2], 'right': {1, 2},
            'empty': 'No sales in this date range.',
        },
        {
            'heading': 'Best Selling Products',
            'headers': ['Product', 'Quantity Sold', 'Revenue'],
            'rows': [[b['product__name'] or 'N/A', ex.num(b['qty'], 1), ex.money(b['revenue'])] for b in best],
            'widths': [3, 1, 2], 'right': {1, 2},
            'empty': 'No product sales in this date range.',
        },
        {
            'heading': 'Orders',
            'note': note,
            'headers': ['Order #', 'Date', 'Customer', 'Payment', 'Status', 'Amount'],
            'rows': [[o.order_number, ex.pretty_dt(o.created_at), o.customer_name, o.get_payment_method_display(),
                      o.get_status_display(), ex.money(o.total_amount)] for o in pdf_orders],
            'widths': [2.2, 2, 2.6, 2.2, 1.6, 1.8], 'right': {5},
            'empty': 'No orders in the selected date range.',
        },
    ]
    return ex.build_pdf(
        f'sales_report_{start}_to_{end}.pdf', 'Sales Report',
        subtitle_lines=[f'Date range: {start:%b %d, %Y} to {end:%b %d, %Y}'],
        kpis=[('Total Sales', ex.money(total_sales)), ('Total Orders', f'{total_orders:,}'), ('Average Order Value', ex.money(average))],
        sections=sections,
    )


@admin_required
def sales_report_export_csv(request):
    start, end, orders = _sales_orders(request)
    rows, total = [], Decimal('0')
    for o in orders:
        d, t = ex.split_datetime(o.created_at)
        total += o.total_amount
        rows.append([
            o.order_number, d, t, o.customer_name, o.customer_email, ex.text_cell(o.customer_phone),
            o.shipping_city, o.get_payment_method_display(), o.get_payment_status_display(), o.get_status_display(),
            o.shipping_fee, o.total_amount,
        ])
    headers = ['Order Number', 'Date', 'Time', 'Customer', 'Email', 'Phone', 'City', 'Payment Method',
               'Payment Status', 'Order Status', 'Shipping Fee (PHP)', 'Total Amount (PHP)']
    pad = [''] * (len(headers) - 2)
    footer = [['TOTAL ORDERS'] + pad + [len(rows)], ['TOTAL SALES'] + pad + [total]]
    return ex.csv_response(f'sales_report_{start}_to_{end}.csv', headers, rows, footer)


# ==========================================================================
# Orders (Manage Orders page) - honours the status/search filters in use
# ==========================================================================
def _filtered_orders(request):
    orders = Order.objects.all().order_by('-created_at')
    status = request.GET.get('status', '').strip()
    search = request.GET.get('search', '').strip()
    if status:
        orders = orders.filter(status=status)
    if search:
        orders = orders.filter(Q(customer_name__icontains=search) | Q(order_number__icontains=search))
    return orders, status, search


@admin_required
def orders_export_pdf(request):
    orders, status, search = _filtered_orders(request)
    order_list = list(orders)
    counted = [o for o in order_list if o.status != 'CANCELLED']
    total_value = sum((o.total_amount for o in counted), Decimal('0'))
    pending = sum(1 for o in order_list if o.status in ('PENDING', 'PENDING_VERIFICATION'))
    processing = sum(1 for o in order_list if o.status == 'PROCESSING')
    delivered = sum(1 for o in order_list if o.status == 'DELIVERED')

    filters = []
    if status:
        filters.append(f'Status: {dict(Order.STATUS_CHOICES).get(status, status)}')
    if search:
        filters.append(f'Search: "{search}"')
    pdf_orders, note = _capped(order_list)
    return ex.build_pdf(
        f'orders_{ex.file_stamp()}.pdf', 'Order Management Report',
        subtitle_lines=[('Filters: ' + ', '.join(filters)) if filters else 'All orders'],
        kpis=[('Orders Listed', f'{len(order_list):,}'), ('Pending', str(pending)), ('Processing', str(processing)),
              ('Delivered', str(delivered)), ('Order Value (excl. cancelled)', ex.money(total_value))],
        sections=[{
            'heading': 'Orders', 'note': note,
            'headers': ['Order #', 'Date', 'Customer', 'City', 'Payment', 'Payment Status', 'Status', 'Total'],
            'rows': [[o.order_number, ex.pretty_dt(o.created_at), o.customer_name, o.shipping_city,
                      o.get_payment_method_display(), o.get_payment_status_display(), o.get_status_display(),
                      ex.money(o.total_amount)] for o in pdf_orders],
            'widths': [2.2, 2, 2.6, 1.8, 2.2, 1.8, 1.7, 1.8], 'right': {7},
            'empty': 'No orders match the current filters.',
        }],
        landscape_mode=True,
    )


@admin_required
def orders_export_csv(request):
    orders, _, _ = _filtered_orders(request)
    rows = []
    for o in orders:
        d, t = ex.split_datetime(o.created_at)
        rows.append([
            o.order_number, d, t, o.customer_name, o.customer_email, ex.text_cell(o.customer_phone),
            o.shipping_address, o.shipping_city, ex.text_cell(o.shipping_postal_code),
            o.get_payment_method_display(), o.get_payment_status_display(), o.get_status_display(),
            o.shipping_fee, o.total_amount,
        ])
    headers = ['Order Number', 'Date', 'Time', 'Customer', 'Email', 'Phone', 'Address', 'City', 'Postal Code',
               'Payment Method', 'Payment Status', 'Order Status', 'Shipping Fee (PHP)', 'Total Amount (PHP)']
    return ex.csv_response(f'orders_{ex.file_stamp()}.csv', headers, rows)


# ==========================================================================
# Production records
# ==========================================================================
def _batch_rows():
    rows = []
    for b in ProductionBatch.objects.select_related('product').order_by('-start_date', '-id'):
        growth = calculate_growth_days(b.start_date, b.harvest_date)
        rows.append({
            'batch': b.batch_number,
            'product': b.product.name if b.product else 'N/A',
            'start': b.start_date,
            'harvest': b.harvest_date,
            'growth': growth,
            'status': b.get_status_display(),
            'cost': b.cost,
            'predicted': b.predicted_yield_kg,
            'actual': b.yield_kg,
        })
    return rows


@admin_required
def production_export_pdf(request):
    rows = _batch_rows()
    harvested = [r for r in rows if r['actual'] is not None]
    total_yield = sum((r['actual'] for r in harvested), Decimal('0'))
    total_cost = sum((r['cost'] for r in rows if r['cost'] is not None), Decimal('0'))
    counts = {s: sum(1 for r in rows if r['status'] == s) for s in ('Growing', 'Ready', 'Harvested')}
    average = total_yield / len(harvested) if harvested else Decimal('0')
    pdf_rows, note = _capped(rows)
    return ex.build_pdf(
        f'production_records_{ex.file_stamp()}.pdf', 'Production Records',
        subtitle_lines=['All production batches, newest first'],
        kpis=[('Total Batches', str(len(rows))), ('Growing', str(counts['Growing'])), ('Ready', str(counts['Ready'])),
              ('Harvested', str(counts['Harvested'])), ('Total Yield', f'{ex.num(total_yield, 2)} kg'),
              ('Total Cost', ex.money(total_cost)), ('Avg Yield / Harvested Batch', f'{ex.num(average, 2)} kg')],
        sections=[{
            'heading': 'Batches', 'note': note,
            'headers': ['Batch No.', 'Product', 'Start', 'Harvest', 'Days', 'Status', 'Cost', 'Predicted (kg)', 'Actual (kg)'],
            'rows': [[r['batch'], r['product'], r['start'] or '-', r['harvest'] or '-',
                      r['growth'] if r['growth'] is not None else '-', r['status'],
                      ex.money(r['cost']) if r['cost'] is not None else '-',
                      ex.num(r['predicted']), ex.num(r['actual'], 3)] for r in pdf_rows],
            'widths': [2.6, 2, 1.5, 1.5, 0.8, 1.2, 1.6, 1.3, 1.3], 'right': {4, 6, 7, 8},
            'empty': 'No production batches recorded yet.',
        }],
        landscape_mode=True,
    )


@admin_required
def production_export_csv(request):
    rows = [[r['batch'], r['product'], r['start'], r['harvest'], r['growth'], r['status'], r['cost'],
             r['predicted'], r['actual']] for r in _batch_rows()]
    headers = ['Batch Number', 'Product', 'Start Date', 'Harvest Date', 'Growth Days', 'Status',
               'Cost (PHP)', 'Predicted Yield (kg)', 'Actual Yield (kg)']
    return ex.csv_response(f'production_records_{ex.file_stamp()}.csv', headers, rows)


# ==========================================================================
# Inventory and Sales
# ==========================================================================
def _inventory_products():
    return Product.objects.all().order_by('name', 'id')


@admin_required
def inventory_export_pdf(request):
    products = list(_inventory_products())
    sales = list(Sale.objects.select_related('product').order_by('-sale_date', '-id'))
    total_stock = sum((p.stock_kg for p in products), Decimal('0'))
    low = sum(1 for p in products if 0 < p.stock_kg < LOW_STOCK_LIMIT)
    revenue = sum((s.total_price for s in sales), Decimal('0'))
    type_labels = dict(Product.PRODUCT_TYPE_CHOICES)
    pdf_sales, note = _capped(sales)
    return ex.build_pdf(
        f'inventory_and_sales_{ex.file_stamp()}.pdf', 'Inventory and Sales',
        kpis=[('Products', str(len(products))), ('Total Stock', ex.num(total_stock, 1)), ('Low Stock Items', str(low)),
              ('Total Sales Records', f'{len(sales):,}'), ('Total Revenue', ex.money(revenue))],
        sections=[
            {
                'heading': 'Current Inventory',
                'headers': ['Product', 'Type', 'Batch ID', 'Unit', 'Price', 'Stock', 'Status', 'Visibility'],
                'rows': [[p.name, type_labels.get(p.product_type, p.product_type), p.batch_id or '-', p.unit,
                          ex.money(p.price_per_kg), ex.num(p.stock_kg, 1), _stock_status(p),
                          'Published' if p.is_active else 'Unpublished'] for p in products],
                'widths': [2.6, 2.2, 1.6, 0.9, 1.5, 1, 1.4, 1.5], 'right': {4, 5},
                'empty': 'No products in inventory.',
            },
            {
                'heading': 'Sales History', 'note': note,
                'headers': ['Sale ID', 'Date', 'Product', 'Quantity', 'Total', 'Source'],
                'rows': [[f'#{s.id}', ex.pretty_dt(s.sale_date), s.product.name, f'{ex.num(s.quantity_kg, 1)} {s.product.unit}',
                          ex.money(s.total_price), s.get_sale_type_display()] for s in pdf_sales],
                'widths': [1, 2.2, 3, 1.6, 1.8, 1.8], 'right': {3, 4},
                'empty': 'No sales recorded yet.',
            },
        ],
        landscape_mode=True,
    )


@admin_required
def inventory_export_csv(request):
    """?dataset=inventory (default) or ?dataset=sales"""
    dataset = request.GET.get('dataset', 'inventory')
    if dataset == 'sales':
        rows = []
        for s in Sale.objects.select_related('product').order_by('-sale_date', '-id'):
            d, t = ex.split_datetime(s.sale_date)
            rows.append([s.id, d, t, s.product.name, s.quantity_kg, s.product.unit, s.total_price, s.get_sale_type_display()])
        headers = ['Sale ID', 'Date', 'Time', 'Product', 'Quantity', 'Unit', 'Total (PHP)', 'Source']
        return ex.csv_response(f'sales_history_{ex.file_stamp()}.csv', headers, rows)

    type_labels = dict(Product.PRODUCT_TYPE_CHOICES)
    rows = [[p.name, type_labels.get(p.product_type, p.product_type), ex.text_cell(p.batch_id), p.unit,
             p.price_per_kg, p.stock_kg, _stock_status(p), 'Published' if p.is_active else 'Unpublished']
            for p in _inventory_products()]
    headers = ['Product', 'Type', 'Batch ID', 'Unit', 'Price (PHP)', 'Stock', 'Stock Status', 'Visibility']
    return ex.csv_response(f'inventory_{ex.file_stamp()}.csv', headers, rows)


# ==========================================================================
# Cooked products
# ==========================================================================
def _cooked_products():
    return Product.objects.filter(product_type='cooked').order_by('name', 'id')


@admin_required
def cooked_export_pdf(request):
    products = list(_cooked_products())
    published = sum(1 for p in products if p.is_active)
    stock_value = sum((p.stock_kg * p.price_per_kg for p in products), Decimal('0'))
    return ex.build_pdf(
        f'cooked_products_{ex.file_stamp()}.pdf', 'Cooked Products',
        subtitle_lines=['Ready-to-eat products'],
        kpis=[('Total Products', str(len(products))), ('Published', str(published)),
              ('Unpublished', str(len(products) - published)), ('Stock Value', ex.money(stock_value))],
        sections=[{
            'heading': 'Products',
            'headers': ['Product', 'Batch ID', 'Unit', 'Price', 'Stock', 'Status', 'Visibility', 'Serving', 'Calories', 'Protein (g)', 'Carbs (g)', 'Fat (g)'],
            'rows': [[p.name, p.batch_id or '-', p.unit, ex.money(p.price_per_kg), ex.num(p.stock_kg, 1), _stock_status(p),
                      'Published' if p.is_active else 'Unpublished', p.serving_size or '-',
                      ex.num(p.calories, 1), ex.num(p.protein, 1), ex.num(p.carbohydrates, 1), ex.num(p.fat, 1)]
                     for p in products],
            'widths': [2.4, 1.4, 0.9, 1.5, 1, 1.3, 1.4, 1.2, 1.1, 1.1, 1.1, 1],
            'right': {3, 4, 8, 9, 10, 11},
            'empty': 'No cooked products yet.',
        }],
        landscape_mode=True,
    )


@admin_required
def cooked_export_csv(request):
    rows = [[p.name, ex.text_cell(p.batch_id), p.unit, p.price_per_kg, p.stock_kg, _stock_status(p),
             'Published' if p.is_active else 'Unpublished', p.description, p.serving_size, p.calories, p.protein,
             p.carbohydrates, p.fat, p.fiber, p.sodium] for p in _cooked_products()]
    headers = ['Product', 'Batch ID', 'Unit', 'Price (PHP)', 'Stock', 'Stock Status', 'Visibility', 'Description',
               'Serving Size', 'Calories', 'Protein (g)', 'Carbohydrates (g)', 'Fat (g)', 'Fiber (g)', 'Sodium (mg)']
    return ex.csv_response(f'cooked_products_{ex.file_stamp()}.csv', headers, rows)


# ==========================================================================
# Environmental readings
# ==========================================================================
def _env_days(request):
    try:
        days = int(request.GET.get('days', 7))
    except (TypeError, ValueError):
        days = 7
    return days if days in (1, 7, 30) else 7


@admin_required
def environment_export_pdf(request):
    days = _env_days(request)
    since = timezone.now() - timedelta(days=days)
    readings = SensorReading.objects.filter(timestamp__gte=since)
    stats = readings.aggregate(
        n=Count('id'), t_avg=Avg('temperature'), t_min=Min('temperature'), t_max=Max('temperature'),
        h_avg=Avg('humidity'), h_min=Min('humidity'), h_max=Max('humidity'), a_avg=Avg('air_quality_ppm'),
    )
    hourly = days == 1
    trunc = TruncHour('timestamp') if hourly else TruncDate('timestamp')
    buckets = readings.annotate(bucket=trunc).values('bucket').annotate(
        n=Count('id'), t_avg=Avg('temperature'), t_min=Min('temperature'), t_max=Max('temperature'),
        h_avg=Avg('humidity'), a_avg=Avg('air_quality_ppm'),
    ).order_by('-bucket')

    def f(value, places=1):
        return ex.num(value, places) if value is not None else '-'

    def label(b):
        return ex.pretty_dt(b) if hourly else b.strftime('%Y-%m-%d')

    span = 'Last 24 hours' if days == 1 else f'Last {days} days'
    return ex.build_pdf(
        f'environment_report_{days}d_{ex.file_stamp()}.pdf', 'Environmental Report',
        subtitle_lines=[f'{span} - averaged {"per hour" if hourly else "per day"}'],
        kpis=[('Readings', f"{stats['n']:,}"),
              ('Avg Temperature', f"{f(stats['t_avg'])} C"), ('Temp Range', f"{f(stats['t_min'])} - {f(stats['t_max'])} C"),
              ('Avg Humidity', f"{f(stats['h_avg'])} %"), ('Humidity Range', f"{f(stats['h_min'])} - {f(stats['h_max'])} %"),
              ('Avg Air Quality', f"{f(stats['a_avg'], 0)} ppm")],
        sections=[{
            'heading': 'Summary by ' + ('Hour' if hourly else 'Day'),
            'headers': ['Period', 'Readings', 'Avg Temp (C)', 'Min Temp (C)', 'Max Temp (C)', 'Avg Humidity (%)', 'Avg Air Quality (ppm)'],
            'rows': [[label(b['bucket']), b['n'], f(b['t_avg']), f(b['t_min']), f(b['t_max']), f(b['h_avg']), f(b['a_avg'], 0)]
                     for b in buckets],
            'widths': [2.2, 1, 1.4, 1.4, 1.4, 1.6, 1.8], 'right': {1, 2, 3, 4, 5, 6},
            'empty': 'No sensor readings in this period.',
        }],
    )


@admin_required
def environment_export_csv(request):
    days = _env_days(request)
    since = timezone.now() - timedelta(days=days)
    rows = []
    for r in SensorReading.objects.filter(timestamp__gte=since).order_by('-timestamp')[:20000]:
        d, t = ex.split_datetime(r.timestamp)
        rows.append([d, t, r.temperature, r.humidity, r.air_quality_ppm, r.co2_ppm, r.device_id])
    headers = ['Date', 'Time', 'Temperature (C)', 'Humidity (%)', 'Air Quality (ppm)', 'CO2 (ppm)', 'Device']
    return ex.csv_response(f'environment_readings_{days}d_{ex.file_stamp()}.csv', headers, rows)


# ==========================================================================
# Analytics (PDF only)
# ==========================================================================
@admin_required
def analytics_export_pdf(request):
    data = json.loads(analytics_api(request).content)
    cards = data['summary_cards']
    charts = data['charts']
    width = 500

    bar = charts['production_bar']
    months = bar['labels']
    series = [(d['label'], d['data']) for d in bar['datasets']]
    pie = charts['production_pie']
    fin = charts['financial']
    fin_summary = charts['financial_summary']
    fin_series = [(d['label'], d['data']) for d in fin['datasets']]
    fin_colors = [d['borderColor'] for d in fin['datasets']]

    monthly_rows = []
    for i, month in enumerate(months):
        values = [s[1][i] for s in series]
        monthly_rows.append([month] + [ex.num(v, 2) for v in values] + [ex.num(sum(values), 2)])
    product_headers = ['Month'] + [name for name, _ in series] + ['Total (kg)']

    fin_rows = []
    for i, month in enumerate(fin['labels']):
        revenue, cost, net = (fin_series[0][1][i], fin_series[1][1][i], fin_series[2][1][i])
        fin_rows.append([month, ex.money(revenue), ex.money(cost), ex.money(net)])

    share_rows = [[l, f'{v:.1f}%'] for l, v in zip(pie['labels'], pie['data'])]

    sections = [
        {
            'heading': 'Monthly Yield by Product (kg)', 'flowable': ex.bar_chart(months, series, width),
            'then': {
                'headers': product_headers, 'rows': monthly_rows,
                'widths': [1.6] + [1.2] * (len(product_headers) - 1), 'right': set(range(1, len(product_headers))),
                'empty': 'No harvested batches in the last 6 months.',
            },
        },
        {
            'heading': 'Yield Share by Product', 'flowable': ex.pie_chart(pie['labels'], pie['data'], width),
            'then': {'headers': ['Product', 'Share of Total Yield'], 'rows': share_rows, 'widths': [3, 1.5],
                     'right': {1}, 'empty': 'No yield data yet.'},
        },
        {
            'heading': 'Revenue vs. Cost', 'flowable': ex.line_chart(fin['labels'], fin_series, width, colors_map=fin_colors),
            'then': {
                'headers': ['Month', 'Revenue', 'Cost', 'Net Profit'], 'rows': fin_rows,
                'widths': [1.6, 1.5, 1.5, 1.5], 'right': {1, 2, 3},
                'empty': 'No revenue or cost data in the last 6 months.',
            },
        },
    ]
    return ex.build_pdf(
        f'analytics_report_{ex.file_stamp()}.pdf', 'Analytics Report',
        subtitle_lines=['Production and financial charts cover the last 6 months; totals cover all time'],
        kpis=[
            ('Avg. Monthly Yield', f"{ex.num(cards['avg_yield'], 2)} kg"),
            ('Avg. Revenue / Month', ex.money(cards['avg_revenue'])),
            ('Batch Success Rate', f"{cards['success_rate']:.1f}%"),
            ('Environmental Stability', f"{cards['env_stability']:.1f}%"),
            ('Total Revenue', ex.money(fin_summary['total_revenue'])),
            ('Total Cost', ex.money(fin_summary['total_cost'])),
            ('Net Profit', ex.money(fin_summary['net_profit'])),
        ],
        sections=sections,
    )
