# Real-time Airfare Price Index for India (CPI Augmentation)

> **Smart India Hackathon 2026 (SIH26056)** &bull; **Team Polarchy**  
> **Problem Statement Title**: Development of a Real-time Airfare Price Index for India through Automated Web Scraping of Airline and Online Travel Aggregator Portals for Augmentation of the Consumer Price Index (CPI).  
> **Organization**: Ministry of Statistics and Programme Implementation (MoSPI), Government of India.  
> **Theme**: Travel & Tourism | **Category**: Software.

Built with **Python 3.14 & Django 6.1**, this system provides an end-to-end econometric platform to collect high-frequency domestic airline fares across India, compute micro-founded elementary and multilateral price indices (Jevons, Dutot, Carli, Fisher, Törnqvist), apply DGCA passenger route weighting, and evaluate the augmentation of the Ministry of Statistics and Programme Implementation (MoSPI) Consumer Price Index (CPI).

---

## 🛫 Features & Capabilities (Polarchy SIH Technical Framework)

1. **Automated Multi-Portal Web Scraping Engine (Steps 01 & 02)**:
   - Scrapes fares across major Indian airlines (**IndiGo, Air India, Air India Express, Akasa Air, SpiceJet**) and Online Travel Aggregators (**MakeMyTrip, Goibibo, Booking.com, Yatra, Cleartrip**).
   - Stratified advance booking horizons ($L \in \{0d, 1-3d, 7-14d, 21-30d\}$).
   - Resilient session handling, anti-bot user-agent rotation, and ethical scraping standards (`robots.txt`).

2. **Data Cleaning & Standardization Pipeline (Steps 03 & 07)**:
   - **Deduplication Engine**: Identifies and prunes redundant quotes matching route, flight number, carrier, and travel date.
   - **Outlier & Anomaly Detection**: Interquartile Range (IQR $1.5\times / 2.5\times$) and Z-score filtering to flag abnormal fare spikes.
   - **Data Quality Monitor** (`/validation/`): Tracks clean data ratio (>98% certified), portal distribution, and outlier logs.

3. **Axiomatic Airfare Price Index (AFPI) Generation (Step 04)**:
   - **Jevons Index** (Geometric mean of price relatives — international CPI standard).
   - **Dutot Index** (Ratio of arithmetic mean prices).
   - **Carli Index** (Arithmetic mean of price relatives — empirically demonstrates the upward Carli bias).
   - **Törnqvist & Fisher Ideal** multilateral indices.
   - **Lead-Horizon Weighting** ($w_L$) & **DGCA City-Pair Route Weights** ($W_r$).

4. **CPI Integration & Dynamic Impact Simulator (Steps 05 & 06)**:
   - Simulates substitution of traditional delayed manual airfare quotes with real-time scraped microdata in the CPI "Transport & Communication" sub-group (3.2% expenditure weight).
   - **Interactive Live Policy Slider**: Adjust $w_{\text{air}}$ from $0.5\%$ to $10.0\%$ to immediately simulate and visualize CPI trajectory changes.

5. **MoSPI Executive Policy Brief Generator (Step 08)**:
   - Print-ready official document at `/reports/mospi-policy-brief/` formatted for MoSPI Advisory Committee and SIH evaluators.

---

## 📂 Project Architecture

```text
Flight Agrigator/
├── manage.py
├── README.md
├── airfare_index/
│   ├── settings.py           # Configured with Asia/Kolkata timezone & core app
│   ├── urls.py               # Root URL configuration
│   └── wsgi.py
├── core/
│   ├── models.py             # Airport, Route, Airline, FlightQuote, AirfarePriceIndex, CPITransportBenchmark, ScrapeJob, DataQualityMetrics
│   ├── views.py              # Dashboard, Methodology, Routes, Scraper, Validation, Policy Brief, APIs, CSV Export
│   ├── urls.py               # Core routing table
│   ├── admin.py              # Full Django admin registrations
│   ├── tests.py              # Unit & integration test suite (8 tests passing)
│   ├── scraper/
│   │   ├── collector.py      # Automated scraping engine with multi-portal rotation
│   │   ├── cleaner.py        # Deduplication & IQR outlier detection pipeline
│   │   ├── dgca_data.py      # Official DGCA domestic route passenger stats & MoSPI baselines
│   │   └── data_seeder.py    # Master reference seeder & multi-month time series generator
│   ├── econometric/
│   │   ├── index_calculator.py # Jevons, Dutot, Carli, Fisher, Törnqvist pipeline
│   │   └── cpi_augmenter.py    # CPI Transport sub-group augmentation & gap analysis
│   ├── management/commands/
│   │   ├── seed_data.py      # CLI: python manage.py seed_data
│   │   └── run_scraper.py    # CLI: python manage.py run_scraper
│   └── templates/
│       ├── base.html         # Tailwind CSS, Chart.js, Navigation header & alerts
│       ├── dashboard.html    # Executive KPI cards & dual-axis time series charts
│       ├── methodology.html  # Formula comparisons & DGCA weights table
│       ├── routes.html       # Route selector & dynamic lead-time curves
│       └── scraper.html      # Job history & live microdata table
```

---

## 🚀 Quickstart & Usage

### 1. Start the Django Development Server
```powershell
python manage.py runserver
```
Then open your browser to **`http://127.0.0.1:8000/`**.

### 2. Default Admin Credentials
- **URL**: `http://127.0.0.1:8000/admin/`
- **Username**: `admin`
- **Password**: `admin123`

### 3. Key Management Commands

- **Seed Reference Data & Historical Time-Series**:
  ```powershell
  python manage.py seed_data --months 6
  ```

- **Run an Automated Scraping & Recalculation Cycle**:
  ```powershell
  python manage.py run_scraper
  ```

- **Run Unit & Integration Tests**:
  ```powershell
  python manage.py test
  ```

---

## 📊 Econometric Formulas Implemented

1. **Jevons Index (Standard for CPI)**:
   $$I_J^{0:t} = \left(\prod_{i=1}^n \frac{p_{i}^t}{p_i^0}\right)^{1/n} = \frac{\exp\left(\frac{1}{n}\sum \ln p_i^t\right)}{\exp\left(\frac{1}{n}\sum \ln p_i^0\right)}$$

2. **Dutot Index**:
   $$I_D^{0:t} = \frac{\frac{1}{n}\sum p_i^t}{\frac{1}{n}\sum p_i^0}$$

3. **Carli Index**:
   $$I_C^{0:t} = \frac{1}{n}\sum_{i=1}^n \left(\frac{p_i^t}{p_i^0}\right)$$

4. **DGCA City-Pair Route Aggregation**:
   $$I_{\text{National}}^{0:t} = \sum_{r} W_r \cdot \left(\sum_L w_L \cdot I_{r, L}^{0:t}\right)$$
