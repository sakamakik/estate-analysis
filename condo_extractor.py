import requests
from bs4 import BeautifulSoup
import re
import pprint
import argparse
import sys
import os
import json
from datetime import datetime
import shutil


def build_centris_url(centris_id: str) -> str:
    """Build the full Centris URL from an ID number."""
    return f"https://www.centris.ca/fr/condo~a-vendre~montreal-ville-marie/{centris_id}"


def normalize_text(text: str) -> str:
    """Normalize extracted text: strip, remove NBSP and excessive whitespace/newlines.

    Returns an empty string for falsy inputs.
    """
    if not text:
        return ""
    # Replace NBSP with regular space, convert multiple whitespace to single space,
    # and strip leading/trailing whitespace/newlines.
    s = text.replace("\xa0", " ")
    s = s.replace("\u00A0", " ")
    # Normalize all whitespace (newlines, tabs) to single spaces
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_number(text: str):
    """Extract first number-like group from a string and return digits-only string, or None."""
    if not text:
        return None
    s = normalize_text(text)
    match = re.search(r'([\d\s.,]+)', s)
    if match:
        num = match.group(1)
        # Remove spaces and commas used as thousands separators
        return re.sub(r"[\s,]", "", num)
    return None

def get_centris_id_from_url(url):
    """Extract Centris ID from URL."""
    match = re.search(r'/(\d+)(?:\?|$)', url)
    return match.group(1) if match else None

def get_cached_data(centris_id):
    """Try to get cached data for a Centris ID."""
    cache_file = os.path.join('data', f'{centris_id}.json')
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def download_primary_photo(centris_id, soup, headers):
    """Download the primary photo from the listing."""
    try:
        # Look for images from Centris media server with specific format
        photo = soup.find('img', src=re.compile(r'https://mspublic\.centris\.ca/media\.ashx.*[?&]t=pi\b'))
            
        if photo:
            photo_url = photo.get('src')
            if photo_url:
                if photo_url.startswith('//'):
                    photo_url = 'https:' + photo_url
                
                # Download the photo
                photo_response = requests.get(photo_url, headers=headers, stream=True)
                photo_response.raise_for_status()
                
                # Save the photo
                photo_path = os.path.join('data', f'{centris_id}.jpeg')
                with open(photo_path, 'wb') as f:
                    shutil.copyfileobj(photo_response.raw, f)
                
                return photo_url
    except Exception as e:
        print(f"Failed to download photo: {str(e)}")
    return None

def save_to_cache(centris_id, data):
    """Save extracted data to cache file."""
    os.makedirs('data', exist_ok=True)
    cache_file = os.path.join('data', f'{centris_id}.json')
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def extract_listing_data(url):
    # Extract Centris ID from URL
    centris_id = get_centris_id_from_url(url)
    if not centris_id:
        raise ValueError("Invalid Centris URL")
    
    # Check cache first
    cached_data = get_cached_data(centris_id)
    if cached_data:
        return cached_data
    
    # If not in cache, fetch from web
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    data = {}

    # Address - try multiple approaches
    address = None
    
    # First try h2 with app. pattern
    for heading in soup.find_all(['h1', 'h2']):
        text = normalize_text(heading.get_text())
        # Look for pattern like "1234, Rue Example, app. 567"
        match = re.search(r'(\d+,\s*(?:Rue|Avenue|Boulevard|Boul\.|Ave\.|Chemin|Ch\.|Place|Pl\.)[^,]+(?:,\s*(?:app\.|appartement)\s*\d+)?)', text, re.IGNORECASE)
        if match:
            address = match.group(1)
            break
    
    # If not found, try meta tags
    if not address:
        for meta in soup.find_all('meta', {'property': ['og:title', 'description']}):
            text = normalize_text(meta.get('content', ''))
            match = re.search(r'(\d+,\s*(?:Rue|Avenue|Boulevard|Boul\.|Ave\.|Chemin|Ch\.|Place|Pl\.)[^,]+(?:,\s*(?:app\.|appartement)\s*\d+)?)', text, re.IGNORECASE)
            if match:
                address = match.group(1)
                break
    
    # Last try: look for address in any tag with specific structure
    if not address:
        address_text = soup.find(string=re.compile(r'\d+,\s*(?:Rue|Avenue|Boulevard|Boul\.|Ave\.|Chemin|Ch\.|Place|Pl\.)', re.IGNORECASE))
        if address_text:
            match = re.search(r'(\d+,\s*(?:Rue|Avenue|Boulevard|Boul\.|Ave\.|Chemin|Ch\.|Place|Pl\.)[^,]+(?:,\s*(?:app\.|appartement)\s*\d+)?)', normalize_text(address_text), re.IGNORECASE)
            if match:
                address = match.group(1)
    
    data["address"] = address

    # Price
    price = soup.find(class_="price")
    if price:
        data["price"] = extract_number(price.get_text())
    else:
        data["price"] = None

    # Bedrooms
    bedrooms = soup.find(class_="cac")
    data["bedrooms"] = extract_number(bedrooms.get_text()) if bedrooms else None

    # Bathrooms
    bathrooms = soup.find(class_="sdb")
    data["bathrooms"] = extract_number(bathrooms.get_text()) if bathrooms else None

    # Square footage - try multiple patterns
    sqft = None
    # First try finding in Caractéristiques section
    caractéristiques = soup.find(string=re.compile("Caractéristiques"))
    if caractéristiques:
        section = caractéristiques.find_parent()
        if section:
            # Look for various superficie patterns in this section
            patterns = [
                r"Superficie (?:habitable|nette|brute)\s*(?::|de)?\s*(\d[\d\s,]+)\s*(?:pc|pi)",
                r"(\d[\d\s,]+)\s*(?:pc|pi)",
                r"Superficie.*?(\d[\d\s,]+)\s*(?:pc|pi)"
            ]
            section_text = normalize_text(section.get_text())
            for pattern in patterns:
                m = re.search(pattern, section_text, flags=re.IGNORECASE)
                if m:
                    sqft = re.sub(r"[\s,]", "", m.group(1))
                    break
    
    # If not found, try searching whole page
    if not sqft:
        full_text = normalize_text(soup.get_text())
        patterns = [
            r"Superficie (?:habitable|nette|brute)\s*(?::|de)?\s*(\d[\d\s,]+)\s*(?:pc|pi)",
            r"(\d[\d\s,]+)\s*(?:pc|pi)\b"
        ]
        for pattern in patterns:
            m = re.search(pattern, full_text, flags=re.IGNORECASE)
            if m:
                sqft = re.sub(r"[\s,]", "", m.group(1))
                break
    
    data["sqft"] = sqft

    # Year of construction
    year = None
    # Try finding in Caractéristiques section first
    caractéristiques = soup.find(string=re.compile("Caractéristiques"))
    if caractéristiques:
        section = caractéristiques.find_parent()
        if section:
            section_text = normalize_text(section.get_text())
            m = re.search(r"Année\s+(?:de\s+)?construction\s*(?::|de)?\s*(\d{4})", section_text, flags=re.IGNORECASE)
            if m:
                year = m.group(1)
    
    # If not found, search whole page
    if not year:
        full_text = normalize_text(soup.get_text())
        m = re.search(r"Année\s+(?:de\s+)?construction\s*(?::|de)?\s*(\d{4})", full_text, flags=re.IGNORECASE)
        if m:
            year = m.group(1)
    
    data["year_of_construction"] = year

    # Financial information extraction (assessments, taxes, fees)
    assess_total = None
    assess_terrain = None
    assess_building = None
    tax_municipal = None
    tax_school = None
    condo_fee = None
    
    # Get full page text once
    full_text = normalize_text(soup.get_text())
    
    # Helper function to find largest number in a list of matches
    def get_largest_number(matches):
        values = [extract_number(m.group(1)) for m in matches if extract_number(m.group(1))]
        return max(values, key=lambda x: int(x)) if values else None
    
    # Municipal assessments
    # Try finding Terrain value (look for number after "Terrain")
    terrain_matches = re.finditer(r"Terrain\s*:?\s*(\d[\d\s,]+)\s*\$", full_text, flags=re.IGNORECASE)
    assess_terrain = get_largest_number(terrain_matches)
    
    # Try finding Bâtiment value
    building_matches = re.finditer(r"Bâtiment\s*:?\s*(\d[\d\s,]+)\s*\$", full_text, flags=re.IGNORECASE)
    assess_building = get_largest_number(building_matches)
    
    # Try finding total value directly
    total_matches = re.finditer(r"(?:Total|Évaluation municipale totale)\s*:?\s*(\d[\d\s,]+)\s*\$", full_text, flags=re.IGNORECASE)
    assess_total = get_largest_number(total_matches)
    
    # If we have terrain and building but no total, calculate it
    if not assess_total and assess_terrain and assess_building:
        assess_total = str(int(assess_terrain) + int(assess_building))
    
    # Taxes
    # Look for municipal taxes with year in parentheses (to get annual amount)
    mun_matches = re.finditer(r"[Mm]unicipales\s*\(\d{4}\)\s*:?\s*(\d[\d\s,]+)\s*\$", full_text)
    tax_municipal = get_largest_number(mun_matches)
    
    # If not found, try without year
    if not tax_municipal:
        mun_matches = re.finditer(r"[Mm]unicipales\s*:?\s*(\d[\d\s,]+)\s*\$", full_text)
        tax_municipal = get_largest_number(mun_matches)
    
    # Same for school taxes
    school_matches = re.finditer(r"[Ss]colaires\s*\(\d{4}\)\s*:?\s*(\d[\d\s,]+)\s*\$", full_text)
    tax_school = get_largest_number(school_matches)
    
    if not tax_school:
        school_matches = re.finditer(r"[Ss]colaires\s*:?\s*(\d[\d\s,]+)\s*\$", full_text)
        tax_school = get_largest_number(school_matches)
    
    # Condo fees - look for annual amount
    fee_matches = re.finditer(r"Frais de copropriété\s*:?\s*(\d[\d\s,]+)\s*\$", full_text)
    condo_fee = get_largest_number(fee_matches)
    
    # Convert annual values to monthly for taxes and fees
    if tax_municipal:
        tax_municipal = str(round(int(tax_municipal) / 12))
    if tax_school:
        tax_school = str(round(int(tax_school) / 12))
    if condo_fee:
        condo_fee = str(round(int(condo_fee) / 12))
    
    # Store results
    data["municipal_assessment_total"] = assess_total
    data["municipal_terrain"] = assess_terrain
    data["municipal_building"] = assess_building
    data["taxes_municipal"] = tax_municipal  # Now monthly
    data["taxes_school"] = tax_school  # Now monthly
    data["condo_fee"] = condo_fee  # Now monthly

    # Download primary photo
    photo_url = download_primary_photo(centris_id, soup, headers)
    
    # Add metadata to the data
    data["url"] = url
    data["centris_id"] = centris_id
    data["extraction_date"] = datetime.now().isoformat()
    data["photo_url"] = photo_url
    data["photo_path"] = f'{centris_id}.jpeg' if photo_url else None
    
    # Save to cache
    save_to_cache(centris_id, data)
    
    return data


if __name__ == "__main__":
    url = "https://www.centris.ca/fr/condo~a-vendre~montreal-ville-marie/16819211"
    info = extract_listing_data(url)
    pprint.pprint(info)
