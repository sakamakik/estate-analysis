import requests
from bs4 import BeautifulSoup
import json

def scrape_centris(url):
    """
    Scrapes a Centris property page for key information.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        data = {}

        # Price
        price_tag = soup.find('span', itemprop='price')
        data['price'] = price_tag['content'] if price_tag else 'Not found'

        # Address
        address_tag = soup.find('h2', itemprop='address')
        data['address'] = address_tag.text.strip() if address_tag else 'Not found'

        # Characteristics (Bedrooms, Bathrooms, etc.)
        for carac in soup.find_all('div', class_='carac-container'):
            for item in carac.find_all('div', class_='carac'):
                label = item.find('div', class_='carac-title').text.strip()
                value = item.find('div', class_='carac-value').text.strip()
                data[label.lower().replace(' ', '_')] = value

        # Financial Details (Taxes, Assessment)
        for fin_item in soup.find_all('div', class_='fin'):
            label_tag = fin_item.find('div', class_='label')
            value_tag = fin_item.find('div', class_='valeur')
            if label_tag and value_tag:
                label = label_tag.text.strip()
                value = value_tag.text.strip()
                if 'Total' in label:
                    parent_container = fin_item.find_parent('div', class_='fin-container')
                    if parent_container:
                        main_label_tag = parent_container.find_previous_sibling('div', class_='text-lg')
                        if main_label_tag:
                            main_label = main_label_tag.text.strip()
                            data[f"{main_label.lower().replace(' ', '_')}_total"] = value
                else:
                    data[label.lower().replace(' ', '_')] = value
        
        # Gross Area (Superficie brute)
        gross_area_tag = soup.find('div', class_='carac-title', string='Superficie brute')
        if gross_area_tag:
            value_tag = gross_area_tag.find_next_sibling('div', class_='carac-value')
            if value_tag:
                data['gross_area_sq_ft'] = value_tag.text.strip()


        return data

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

if __name__ == '__main__':
    url = "https://www.centris.ca/fr/condo~a-vendre~montreal-ville-marie/10180103?uc=0"
    scraped_data = scrape_centris(url)
    
    if "error" in scraped_data:
        print(f"Error: {scraped_data['error']}")
    else:
        print(json.dumps(scraped_data, indent=4, ensure_ascii=False))
