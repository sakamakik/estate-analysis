import requests
from bs4 import BeautifulSoup

def scrape_website(url):
    """
    Scrapes a website and returns the title, address, and other details.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.text, 'html.parser')
        with open("soup_output.html", "w", encoding="utf-8") as f:
            f.write(soup.prettify())
        
    except requests.exceptions.RequestException as e:
        return {
            "error": str(e)
        }

if __name__ == '__main__':
    # Example usage
    test_url = "https://www.centris.ca/fr/condo~a-vendre~montreal-ville-marie/16490225"
    scraped_data = scrape_website(test_url)
    if "error" in scraped_data:
        print(f"Error scraping {test_url}: {scraped_data['error']}")
    else:
        for key, value in scraped_data.items():
            print(f"{key.replace('_', ' ').title()}: {value}")

