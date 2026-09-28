from django.urls import path
from core import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('methodology/', views.methodology_view, name='methodology'),
    path('routes/', views.routes_view, name='routes'),
    path('scraper/', views.scraper_view, name='scraper'),
    path('validation/', views.validation_view, name='validation'),
    path('stress-test/', views.stress_test_view, name='stress_test'),
    path('hedonic/', views.hedonic_view, name='hedonic'),
    path('reports/mospi-policy-brief/', views.policy_report_view, name='policy_report'),
    
    # Action triggers
    path('actions/trigger-scrape/', views.trigger_scrape_view, name='trigger_scrape'),
    path('actions/recalculate-indices/', views.recalculate_indices_view, name='recalculate_indices'),
    
    # APIs & Export
    path('api/indices/', views.api_indices, name='api_indices'),
    path('api/cpi-benchmark/', views.api_cpi_benchmark, name='api_cpi_benchmark'),
    path('api/cpi-simulate/', views.api_cpi_simulate, name='api_cpi_simulate'),
    path('api/stress-test/', views.api_stress_test, name='api_stress_test'),
    path('api/validation-stats/', views.api_validation_stats, name='api_validation_stats'),
    path('export/quotes-csv/', views.export_quotes_csv, name='export_quotes_csv'),
]
