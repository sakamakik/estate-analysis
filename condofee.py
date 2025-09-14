import requests
from bs4 import BeautifulSoup

def get_condo_fee(url):
    headers = {
        # It’s polite (and sometimes necessary) to set a realistic User-Agent
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
                      ' Chrome/115.0 Safari/537.36'
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()  # ensure HTTP 200
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find the section that has “Frais de copropriété”
    # Based on inspection, it's under “Détails financiers” -> “Frais de copropriété”
    
    # One strategy: search for a tag containing the text "Frais de copropriété"
    fee_label = soup.find(lambda tag: tag.name in ['span', 'div', 'p', 'li'] 
                         and 'Frais de copropriété' in tag.get_text())
    if fee_label is None:
        return None
    
    # Once we find the label, get a neighboring tag that has the number
    # For example, the label and its sibling or parent might have the fee value.
    text = fee_label.get_text()
    
    # Try to extract the number from the text
    # e.g. "Frais de copropriété  719 $"
    import re
    m = re.search(r'Frais de copropriété\s*([\d\s.,]+)\s*\$', text)
    if m:
        fee = m.group(1).strip()
        # Clean formatting (remove spaces, handle comma/period)
        fee = fee.replace(' ', '').replace(',', '')
        return int(fee)
    
    # If not in same tag, maybe in sibling tags:
    # Example: label tag parent, find next tags
    parent = fee_label.parent
    # you might search children/siblings of parent for the number
    text_all = parent.get_text()
    m2 = re.search(r'Frais de copropriété\s*([\d\s.,]+)\s*\$', text_all)
    if m2:
        fee = m2.group(1).strip()
        fee = fee.replace(' ', '').replace(',', '')
        return int(fee)
    
    return None

if __name__ == "__main__":
    url = "https://www.centris.ca/fr/condo~a-vendre~montreal-ville-marie/10180103?uc=0"
    fee = get_condo_fee(url)
    if fee:
        print(f"Condo fee: ${fee}")
    else:
        print("Could not find the condo fee on that page.")