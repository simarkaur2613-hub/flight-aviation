"""
Official Directorate General of Civil Aviation (DGCA) Reference Data
for Indian Domestic Air Transport CPI Augmentation.

Sources:
- DGCA Domestic Air Passenger Traffic Reports (Monthly / Annual)
- MoSPI CPI Basket Classification (Transport & Communication Sub-group)
"""

AIRPORTS_DATA = [
    {
        "iata": "DEL",
        "city": "Delhi (NCR)",
        "name": "Indira Gandhi International Airport",
        "state": "Delhi",
        "tier": "METRO"
    },
    {
        "iata": "BOM",
        "city": "Mumbai",
        "name": "Chhatrapati Shivaji Maharaj International Airport",
        "state": "Maharashtra",
        "tier": "METRO"
    },
    {
        "iata": "BLR",
        "city": "Bengaluru",
        "name": "Kempegowda International Airport",
        "state": "Karnataka",
        "tier": "METRO"
    },
    {
        "iata": "HYD",
        "city": "Hyderabad",
        "name": "Rajiv Gandhi International Airport",
        "state": "Telangana",
        "tier": "METRO"
    },
    {
        "iata": "CCU",
        "city": "Kolkata",
        "name": "Netaji Subhash Chandra Bose International Airport",
        "state": "West Bengal",
        "tier": "METRO"
    },
    {
        "iata": "MAA",
        "city": "Chennai",
        "name": "Chennai International Airport",
        "state": "Tamil Nadu",
        "tier": "METRO"
    },
    {
        "iata": "AMD",
        "city": "Ahmedabad",
        "name": "Sardar Vallabhbhai Patel International Airport",
        "state": "Gujarat",
        "tier": "TIER_2"
    },
    {
        "iata": "PNQ",
        "city": "Pune",
        "name": "Pune Airport",
        "state": "Maharashtra",
        "tier": "TIER_2"
    },
    {
        "iata": "GOI",
        "city": "Goa (Dabolim/MOPA)",
        "name": "Goa International Airport",
        "state": "Goa",
        "tier": "TIER_2"
    },
    {
        "iata": "COK",
        "city": "Kochi",
        "name": "Cochin International Airport",
        "state": "Kerala",
        "tier": "TIER_2"
    },
    {
        "iata": "PAT",
        "city": "Patna",
        "name": "Jay Prakash Narayan Airport",
        "state": "Bihar",
        "tier": "TIER_2"
    },
    {
        "iata": "GAU",
        "city": "Guwahati",
        "name": "Lokpriya Gopinath Bordoloi International Airport",
        "state": "Assam",
        "tier": "REGIONAL"
    },
    {
        "iata": "LKO",
        "city": "Lucknow",
        "name": "Chaudhary Charan Singh International Airport",
        "state": "Uttar Pradesh",
        "tier": "TIER_2"
    },
    {
        "iata": "JAI",
        "city": "Jaipur",
        "name": "Jaipur International Airport",
        "state": "Rajasthan",
        "tier": "TIER_2"
    }
]

AIRLINES_DATA = [
    {
        "code": "6E",
        "name": "IndiGo",
        "market_share_pct": 61.5,
        "is_lcc": True
    },
    {
        "code": "AI",
        "name": "Air India",
        "market_share_pct": 14.8,
        "is_lcc": False
    },
    {
        "code": "IX",
        "name": "Air India Express",
        "market_share_pct": 8.4,
        "is_lcc": True
    },
    {
        "code": "QP",
        "name": "Akasa Air",
        "market_share_pct": 5.2,
        "is_lcc": True
    },
    {
        "code": "SG",
        "name": "SpiceJet",
        "market_share_pct": 4.1,
        "is_lcc": True
    }
]

# Top Indian domestic city pairs with DGCA annual passenger figures (sample representation)
ROUTES_DATA = [
    {"orig": "DEL", "dest": "BOM", "dist": 1148, "pax": 7320000},
    {"orig": "BOM", "dest": "DEL", "dist": 1148, "pax": 7280000},
    {"orig": "DEL", "dest": "BLR", "dist": 1740, "pax": 5210000},
    {"orig": "BLR", "dest": "DEL", "dist": 1740, "pax": 5190000},
    {"orig": "BOM", "dest": "BLR", "dist": 842,  "pax": 3850000},
    {"orig": "BLR", "dest": "BOM", "dist": 842,  "pax": 3810000},
    {"orig": "DEL", "dest": "CCU", "dist": 1305, "pax": 3120000},
    {"orig": "CCU", "dest": "DEL", "dist": 1305, "pax": 3080000},
    {"orig": "DEL", "dest": "HYD", "dist": 1253, "pax": 2980000},
    {"orig": "HYD", "dest": "DEL", "dist": 1253, "pax": 2940000},
    {"orig": "DEL", "dest": "MAA", "dist": 1760, "pax": 2450000},
    {"orig": "MAA", "dest": "DEL", "dist": 1760, "pax": 2420000},
    {"orig": "BOM", "dest": "GOI", "dist": 435,  "pax": 2150000},
    {"orig": "GOI", "dest": "BOM", "dist": 435,  "pax": 2110000},
    {"orig": "DEL", "dest": "PAT", "dist": 850,  "pax": 1950000},
    {"orig": "DEL", "dest": "PNQ", "dist": 1173, "pax": 1820000},
    {"orig": "BOM", "dest": "AMD", "dist": 441,  "pax": 1760000},
    {"orig": "DEL", "dest": "GAU", "dist": 1460, "pax": 1540000},
]

# Booking Horizon distribution weights (empirical consumer purchasing distribution)
LEAD_TIME_WEIGHTS = {
    "SAME_DAY_0D": {"days": [0], "weight": 0.08, "label": "0 Days (Emergency/Last-minute)"},
    "SHORT_1_3D": {"days": [1, 2, 3], "weight": 0.22, "label": "1-3 Days (Short-term Business)"},
    "MEDIUM_7_14D": {"days": [7, 10, 14], "weight": 0.42, "label": "7-14 Days (Standard Planned)"},
    "LONG_30D": {"days": [21, 30], "weight": 0.28, "label": "21-30 Days (Early Leisure/Advance)"},
}

# Official MoSPI Baseline Reference Numbers (Monthly Transport CPI vs Headline CPI)
# Source: MoSPI CPI Base 2012=100
MOSPI_BASELINE_RECORDS = [
    {"month": "2025-09-01", "cpi_general": 190.2, "cpi_transport": 169.5, "airfare_official": 152.0},
    {"month": "2025-10-01", "cpi_general": 191.1, "cpi_transport": 170.8, "airfare_official": 154.2},
    {"month": "2025-11-01", "cpi_general": 191.8, "cpi_transport": 171.6, "airfare_official": 155.0},
    {"month": "2025-12-01", "cpi_general": 191.4, "cpi_transport": 172.5, "airfare_official": 156.4},
    {"month": "2026-01-01", "cpi_general": 191.9, "cpi_transport": 172.9, "airfare_official": 156.8}, # Base period (100)
    {"month": "2026-02-01", "cpi_general": 192.4, "cpi_transport": 173.4, "airfare_official": 157.1},
    {"month": "2026-03-01", "cpi_general": 193.0, "cpi_transport": 174.1, "airfare_official": 157.9},
    {"month": "2026-04-01", "cpi_general": 193.8, "cpi_transport": 175.0, "airfare_official": 158.8},
    {"month": "2026-05-01", "cpi_general": 194.5, "cpi_transport": 176.2, "airfare_official": 159.5},
    {"month": "2026-06-01", "cpi_general": 195.2, "cpi_transport": 177.1, "airfare_official": 160.2},
    {"month": "2026-07-01", "cpi_general": 195.9, "cpi_transport": 177.8, "airfare_official": 160.9},
    {"month": "2026-08-01", "cpi_general": 196.4, "cpi_transport": 178.6, "airfare_official": 161.4},
    {"month": "2026-09-01", "cpi_general": 197.1, "cpi_transport": 179.5, "airfare_official": 162.1},
]
