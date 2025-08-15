import time, pickle, json, re, random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from twilio.rest import Client
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
from dotenv import load_dotenv
import undetected_chromedriver as uc
import zipfile

def human_sleep(min_seconds=1, max_seconds=3):
    """Sleep for a random duration to mimic human behavior"""
    sleep_time = random.uniform(min_seconds, max_seconds)
    time.sleep(sleep_time)

# Port rotation globals
PORTS = [8001, 8002, 8003, 8004, 8005,8006,8007,8008,8009,8010]
current_port_index = 0
last_port_change_time = time.time()
PORT_CHANGE_INTERVAL = random.randint(3*3600, 4*3600)  # 5-6 hours in seconds

def get_current_port():
    """Get current port and check if rotation is needed"""
    global current_port_index, last_port_change_time, PORT_CHANGE_INTERVAL
    
    current_time = time.time()
    
    # Check if it's time to rotate ports (5-6 hours have passed)
    if current_time - last_port_change_time >= PORT_CHANGE_INTERVAL:
        current_port_index = (current_port_index + 1) % len(PORTS)
        last_port_change_time = current_time
        PORT_CHANGE_INTERVAL = random.randint(5*3600, 6*3600)  # Set new random interval for next rotation
        print(f"[+] Port rotated to {PORTS[current_port_index]} (next rotation in {PORT_CHANGE_INTERVAL/3600:.1f} hours)")
    
    return PORTS[current_port_index]

def create_proxy_extension():
        """Create a Chrome extension for proxy authentication with dynamic port"""
        current_port = get_current_port()
        
        # Create extension directory
        extension_dir = os.path.join(os.getcwd(), 'proxy_extension')
        if not os.path.exists(extension_dir):
            os.makedirs(extension_dir)
        
        # Create manifest.json
        manifest = {
    "version": "1.0.0",
    "manifest_version": 3,
    "name": "Proxy Auth Extension",
    "permissions": [
        "proxy",
        "tabs",
        "storage",
        "webRequest",
        "declarativeNetRequest"
    ],
    "host_permissions": [
        "<all_urls>"
    ],
    "background": {
        "service_worker": "background.js"
    },
    "minimum_chrome_version": "88.0.0"
}
        
        with open(os.path.join(extension_dir, 'manifest.json'), 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Create background.js with dynamic port
        background_js = f"""
// Manifest V3 Service Worker for Proxy Authentication
const config = {{
  mode: "fixed_servers",
  rules: {{
    singleProxy: {{
      scheme: "http",
      host: "isp.oxylabs.io",
      port: {int(current_port)}
    }},
    bypassList: ["localhost"]
  }}
}};

// Set proxy configuration when service worker starts
chrome.proxy.settings.set({{ value: config, scope: "regular" }}, function() {{
  console.log("Proxy configuration set");
}});

// Handle authentication requests
chrome.webRequest.onAuthRequired.addListener(
  function(details) {{
    console.log("Auth required for:", details.url);
    return {{
      authCredentials: {{
        username: "country-US",
        password: ""
      }}
    }};
  }},
  {{ urls: ["<all_urls>"] }},
  ["blocking"]
);

// Re-establish proxy settings when service worker wakes up
chrome.runtime.onStartup.addListener(() => {{
  chrome.proxy.settings.set({{ value: config, scope: "regular" }}, function() {{
    console.log("Proxy configuration restored on startup");
  }});
}});

// Re-establish proxy settings when extension is installed/enabled
chrome.runtime.onInstalled.addListener(() => {{
  chrome.proxy.settings.set({{ value: config, scope: "regular" }}, function() {{
    console.log("Proxy configuration set on install");
  }});
}});
"""

        
        with open(os.path.join(extension_dir, 'background.js'), 'w') as f:
            f.write(background_js)
        
        # Create zip file
        extension_zip = os.path.join(os.getcwd(), 'proxy_auth_extension.zip')
        with zipfile.ZipFile(extension_zip, 'w') as zipf:
            zipf.write(os.path.join(extension_dir, 'manifest.json'), 'manifest.json')
            zipf.write(os.path.join(extension_dir, 'background.js'), 'background.js')
        
        print(f"[+] Proxy extension created with port {current_port}")
        extension_path = extension_dir
        return extension_dir

def load_or_login_facebook(driver, cookie_path="fb_cookies.pkl"):
    driver.get("https://www.facebook.com")
    human_sleep(3, 5)

    def is_logged_in():
        driver.get("https://www.facebook.com/me")
        human_sleep(4, 6)
        return "login" not in driver.current_url.lower()

    if os.path.exists(cookie_path):
        print("[+] Loading Facebook session from cookies...")
        with open(cookie_path, "rb") as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            if "sameSite" in cookie and cookie["sameSite"] == "None":
                cookie["sameSite"] = "Strict"
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"[!] Failed to add cookie: {e}")
        driver.refresh()
        human_sleep(4, 7)

        # Check if cookies still work
        if is_logged_in():
            print("[+] Logged in using cookies.")
            return
        else:
            print("[-] Cookies expired or invalid. Proceeding with manual login...")

    # Manual login
    print("[*] Please log in manually in the browser window.")
    driver.get("https://www.facebook.com")
    input(">>> Press Enter after you've logged in successfully...")

    # Verify login success
    if not is_logged_in():
        raise Exception("[-] Login failed. Check for CAPTCHA or login errors.")
    
    # Save new cookies
    cookies = driver.get_cookies()
    with open(cookie_path, "wb") as f:
        pickle.dump(cookies, f)
    print("[+] Logged in and session cookies saved for future use.")




load_dotenv()

def send_sms(message, phone_number):
    from twilio.rest import Client
    account_sid = 'AC5ff00c97faae9cb8c336341910defe3f'
    auth_token = 'f5ac81997013ed3b13e3f1ade9a9d7c9'
    client = Client(account_sid, auth_token)
    message = client.messages.create(
    from_='+18882810403',
    body=message,
    to=phone_number
    )
    print(f"✅ Message sent! SID: {message.sid}")

def extract_price(text):
    """
    Find first occurrence of $###,### and return it as int.
    """
    m = re.search(r'\$\s*([\d,]+)', text)
    if m:
        return int(m.group(1).replace(',', ''))
    return None

def matches_required_fields(vehicle_details, client):
    """
    Ensure vehicle matches client's required fields, either directly or via seller description fallback.
    """
    desc = vehicle_details.get('seller_description', '').lower()

    def field_matches(field_name, client_key):
        required_val = client.get(client_key)
        if not required_val:
            return True  # Not a required field
        actual_val = vehicle_details.get(field_name)
        if actual_val and required_val.lower() in actual_val.lower():
            return True
        return required_val.lower() in desc

    checks = [
        field_matches('transmission', 'Transmission'),
        field_matches('fuel_type', 'Fuel_Type')
    ]

    return all(checks)
def extract_item_id(href):
    """Extract item ID from Facebook Marketplace URL"""
    if not href:
        return None
    match = re.search(r'/marketplace/item/(\d+)', href)
    if match:
        return match.group(1)
    return None

def extract_miles(text):
    """
    Extract mileage in integer form from various formats like '123,456 miles', '150k miles', or '150 K'.
    """
    if isinstance(text, list):
        text = ' '.join(text)
    
    # First try standard format like 123,456 miles
    m = re.search(r'([\d,]+)\s*miles', text, re.IGNORECASE)
    if m:
        return int(m.group(1).replace(',', ''))
    
    # Now try formats like 150k, 150 k miles
    m = re.search(r'(\d+(?:\.\d+)?)\s*[kK]', text)
    if m:
        return int(float(m.group(1)) * 1000)
    
    return None


def extract_vehicle_details(driver):
    """
    Extract comprehensive vehicle details from Facebook Marketplace listing.
    Returns a dictionary with all available vehicle information.
    """
    vehicle_details = {}
    
    try:
        # Extract mileage
        try:
            mileage_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Driven') and contains(text(), 'miles')]")
            mileage_text = mileage_element.text
            miles = extract_miles(mileage_text)
            vehicle_details['miles'] = miles
            # print(f"[+] Mileage: {miles:,} miles" if miles else "[-] Mileage not found")
        except:
            vehicle_details['miles'] = None
            # print("[-] Mileage element not found")

        # Extract transmission
        try:
            transmission_element = driver.find_element(By.XPATH, "//span[contains(text(), 'transmission')]")
            vehicle_details['transmission'] = transmission_element.text.strip()
            # print(f"[+] Transmission: {vehicle_details['transmission']}")
        except:
            vehicle_details['transmission'] = None
            # print("[-] Transmission not found")

        # Extract exterior and interior colors
        try:
            color_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Exterior colour') or contains(text(), 'Interior colour')]")
            color_text = color_element.text
            if 'Exterior colour:' in color_text and 'Interior colour:' in color_text:
                colors = color_text.split('·')
                exterior = colors[0].replace('Exterior colour:', '').strip()
                interior = colors[1].replace('Interior colour:', '').strip()
                vehicle_details['exterior_color'] = exterior
                vehicle_details['interior_color'] = interior
                # print(f"[+] Colors - Exterior: {exterior}, Interior: {interior}")
            else:
                vehicle_details['exterior_color'] = None
                vehicle_details['interior_color'] = None
        except:
            vehicle_details['exterior_color'] = None
            vehicle_details['interior_color'] = None
            # print("[-] Color information not found")

        # Extract fuel type
        try:
            fuel_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Fuel type:')]")
            fuel_text = fuel_element.text.replace('Fuel type:', '').strip()
            vehicle_details['fuel_type'] = fuel_text
            # print(f"[+] Fuel type: {fuel_text}")
        except:
            vehicle_details['fuel_type'] = None
            # print("[-] Fuel type not found")

        # Extract number of owners
        try:
            owner_element = driver.find_element(By.XPATH, "//span[contains(text(), 'owner')]")
            owner_text = owner_element.text
            owners = re.search(r'(\d+)\s*owner', owner_text)
            vehicle_details['owners'] = int(owners.group(1)) if owners else None
            # print(f"[+] Number of owners: {vehicle_details['owners']}")
        except:
            vehicle_details['owners'] = None
            # print("[-] Owner information not found")

        # Extract payment status
        try:
            payment_element = driver.find_element(By.XPATH, "//span[contains(text(), 'paid off')]")
            vehicle_details['paid_off'] = True
            # print("[+] Vehicle is paid off")
        except:
            vehicle_details['paid_off'] = False
            # print("[-] Payment status not found or not paid off")

        # Extract vehicle history
        try:
            history_element = driver.find_element(By.XPATH, "//span[contains(text(), 'Clear history')]")
            vehicle_details['clear_history'] = True
            # print("[+] Clear history")
            
            # Try to get the detailed history description
            try:
                history_desc = driver.find_element(By.XPATH, "//span[contains(text(), 'no significant damage')]")
                vehicle_details['history_description'] = history_desc.text
                # print(f"[+] History details: {history_desc.text}")
            except:
                vehicle_details['history_description'] = "Clear history"
        except:
            vehicle_details['clear_history'] = False
            vehicle_details['history_description'] = "Unknown"
            # print("[-] History information not found")

        # Extract seller description with "See more" handling
        try:
            seller_desc_text = ""
            
            # FIRST: Find seller description spans that contain truncated text and "See more" buttons
            try:
                # Look for seller description spans with the specific class structure
                desc_spans = driver.find_elements(By.XPATH, 
                    "//span[@class='x193iq5w xeuugli x13faqbe x1vvkbs x1xmvt09 x1lliihq x1s928wv xhkezso x1gmr53x x1cpjm7i x1fgarty x1943h6x xudqn12 x3x7a5m x6prxxf xvq8zen xo1l8bm xzsf02u'][@dir='auto']")
                
                # Also try a more generic approach
                if not desc_spans:
                    desc_spans = driver.find_elements(By.XPATH, 
                        "//span[@dir='auto' and contains(@class, 'x193iq5w') and string-length(text()) > 50]")
                
                for span in desc_spans:
                    span_text = span.text.strip()
                    
                    # Check if this span looks like a seller description (contains car-related content)
                    if (span_text and len(span_text) > 50 and 
                        ('selling' in span_text.lower() or 'car' in span_text.lower() or 
                         'vehicle' in span_text.lower() or 'toyota' in span_text.lower() or
                         'honda' in span_text.lower() or 'acura' in span_text.lower() or
                         'miles' in span_text.lower() or 'engine' in span_text.lower()) and
                        'About this vehicle' not in span_text and
                        'safety rating' not in span_text):
                        
                        # print(f"[+] Found potential seller description span: {span_text[:100]}...")
                        
                        # Look for "See more" button within this span
                        try:
                            see_more_button = span.find_element(By.XPATH, 
                                ".//div[@role='button']//span[contains(text(), 'See more')]")
                            
                            if see_more_button:
                                # print("[+] Found 'See more' button, attempting to click...")
                                
                                # Scroll the button into view
                                driver.execute_script("arguments[0].scrollIntoView(true);", see_more_button)
                                human_sleep(0.3, 0.8)
                                
                                # Try to click the "See more" button (click the parent div with role="button")
                                button_div = see_more_button.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
                                
                                try:
                                    if button_div.is_displayed() and button_div.is_enabled():
                                        button_div.click()
                                        # print("[+] Clicked 'See more' button")
                                        human_sleep(0.8, 1.5)  # Wait for content to expand
                                    else:
                                        # Try JavaScript click
                                        driver.execute_script("arguments[0].click();", button_div)
                                        # print("[+] Clicked 'See more' button via JavaScript")
                                        human_sleep(0.8, 1.5)
                                except Exception as click_e:
                                    # print(f"[-] Failed to click 'See more' button: {click_e}")
                                    # Try clicking the span itself
                                    try:
                                        driver.execute_script("arguments[0].click();", see_more_button)
                                        print("[+] Clicked 'See more' span via JavaScript")
                                        human_sleep(1.5, 2.5)
                                    except:
                                        print("[-] All click attempts failed")
                                
                                # After clicking, re-get the text from the same span
                                try:
                                    expanded_text = span.text.strip()
                                    if expanded_text and len(expanded_text) > len(span_text):
                                        seller_desc_text = expanded_text
                                        # print(f"[+] Successfully expanded description to {len(expanded_text)} characters")
                                        break
                                    else:
                                        # If expansion didn't work, use original text
                                        seller_desc_text = span_text
                                        # print("[-] Description didn't expand, using original text")
                                        break
                                except:
                                    seller_desc_text = span_text
                                    break
                            else:
                                # No "See more" button found, use the text as is
                                seller_desc_text = span_text
                                # print("[+] No 'See more' button found, using available text")
                                break
                                
                        except Exception as see_more_e:
                            # No "See more" button in this span, use the text as is
                            seller_desc_text = span_text
                            # print(f"[+] Using seller description without expansion: {len(span_text)} characters")
                            break
                            
            except Exception as e:
                print(f"[-] Error in seller description extraction: {e}")
            if vehicle_details.get('miles') is  None:
                vehicle_details['miles'] = extract_miles(vehicle_details['seller_description']) if vehicle_details.get('seller_description') else None
            # Clean up the extracted text
            if seller_desc_text:
                # Remove "See more" and "See less" text if still present
                seller_desc_text = re.sub(r'\s*See more\s*', '', seller_desc_text, flags=re.IGNORECASE)
                seller_desc_text = re.sub(r'\s*See less\s*', '', seller_desc_text, flags=re.IGNORECASE)
                seller_desc_text = seller_desc_text.strip()
            
            vehicle_details['seller_description'] = seller_desc_text if seller_desc_text else "No description found"
            
            # if seller_desc_text:
            #     # print(f"[+] Final seller description extracted ({len(seller_desc_text)} characters)")
            #     print(f"[+] Description preview: {seller_desc_text[:100]}...")
            # else:
            #     print("[-] Seller description not found")
                
        except Exception as e:
            vehicle_details['seller_description'] = "No description found"
            print(f"[-] Seller description extraction failed: {e}")

    except Exception as e:
        print(f"[-] Error extracting vehicle details: {e}")
    
    return vehicle_details

def matches_filters(vehicle_details, client):
    """
    Enhanced filter matching using extracted vehicle details.
    """
    # Check avoid keywords in seller description (now a string instead of list)
    seller_desc = vehicle_details.get('seller_description', '')
    if seller_desc and seller_desc != "No description found":
        for kw in client.get("avoid_keywords", []):
            if re.search(re.escape(kw), seller_desc, re.IGNORECASE):
                return False
    
    # Check make/model (this would need to be implemented based on your needs)
    model = client.get("make_model", "").lower()
    if model:
        # You might want to check title or other fields for make/model
        # This depends on how you want to implement make/model matching
        if model not in vehicle_details.get('title', '').lower():
            return False
    
    return True


    # options.add_argument("--headless")  # Do not use headless if login requires CAPTCHA or visual check

# Global driver variable to track if we need to restart browser
driver = None
last_driver_restart = time.time()

def get_driver():
    """Get driver instance, restart if port rotation requires it"""
    global driver, last_driver_restart, last_port_change_time
    
    # Check if we need to restart driver due to port change
    if driver is None or last_port_change_time > last_driver_restart:
        if driver:
            try:
                driver.quit()
                print(f"[+] Closed previous driver from port rotation")
            except:
                pass
      
        # Recreate extension with new port
        extension_path = create_proxy_extension()
        options = uc.ChromeOptions()
        options.add_argument(f'--load-extension={extension_path}')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions-except={}'.format(extension_path))
        options.add_argument('--disable-plugins-discovery')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        
        driver = uc.Chrome(options=options)
        last_driver_restart = time.time()
        print(f"[+] New driver created with port {get_current_port()}")
        
        # Re-login to Facebook after driver restart
        load_or_login_facebook(driver)
    
    return driver

def load_matched_listings():
    """Load matched listings from file, create empty dict if file doesn't exist."""
    try:
        with open("matched_listings.json", "r") as f:
            matched_listings = json.load(f)
        print(f"[+] Loaded matched listings from file.")
        return matched_listings
    except FileNotFoundError:
        print("[+] No previous matched listings found, starting fresh.")
        return {}
    except Exception as e:
        print(f"[-] Error loading matched listings: {e}")
        return {}

def save_matched_listings(matched_listings):
    """Save matched listings to file."""
    try:
        with open("matched_listings.json", "w") as f:
            json.dump(matched_listings, f, indent=4)
        print("[+] Matched listings saved to file.")
    except Exception as e:
        print(f"[-] Error saving matched listings: {e}")

def load_visited_links():
    """Load visited item IDs from file, create empty dict if file doesn't exist."""
    try:
        with open("visited_items.json", "r") as f:
            visited_links = json.load(f)
        print(f"[+] Loaded visited item IDs from file.")
        return visited_links
    except FileNotFoundError:
        print("[+] No previous visited item IDs found, starting fresh.")
        return {}
    except Exception as e:
        print(f"[-] Error loading visited item IDs: {e}")
        return {}

def save_visited_links(visited_links):
    """Save visited item IDs to file."""
    try:
        with open("visited_items.json", "w") as f:
            json.dump(visited_links, f, indent=4)
        print("[+] Visited item IDs saved to file.")
    except Exception as e:
        print(f"[-] Error saving visited item IDs: {e}")

def is_item_visited(item_id, client_phone_make):
    """Check if an item ID has been visited for a specific client."""
    global visited_links
    if not item_id:
        return False
    return item_id in visited_links.get(client_phone_make, [])

def mark_item_visited(item_id, client_phone_make):
    """Mark an item ID as visited for a specific client."""
    global visited_links
    if not item_id:
        return
    if client_phone_make not in visited_links:
        visited_links[client_phone_make] = []
    if item_id not in visited_links[client_phone_make]:
        visited_links[client_phone_make].append(item_id)
        save_visited_links(visited_links)

def cleanup_old_visited_links(max_items_per_client=500):
    """Remove oldest visited item IDs if a client has too many (optional optimization)."""
    global visited_links
    cleaned = False
    for client_phone in visited_links:
        if len(visited_links[client_phone]) > max_items_per_client:
            # Keep only the most recent item IDs (FIFO - remove oldest)
            items_to_remove = len(visited_links[client_phone]) - max_items_per_client
            visited_links[client_phone] = visited_links[client_phone][items_to_remove:]
            print(f"[+] Cleaned up {items_to_remove} old visited item IDs for client {client_phone}")
            cleaned = True
    
    if cleaned:
        save_visited_links(visited_links)

# Initialize driver and login
driver = get_driver()
matched_listings = load_matched_listings()
visited_links = load_visited_links()  # Now stores item IDs instead of full URLs

while True:
    
    # Cleanup old visited item IDs to prevent file from growing too large
    cleanup_old_visited_links()
    
    try:
        with open("clients.json", "r") as f:
            clients = json.load(f)
        print(f"[+] Loaded {len(clients)} clients.")
    except Exception as e:
        print(f"[-] Failed to load clients.json: {e}")
        time.sleep(60)
        continue  # Try again in the next round
    # Updated main loop
    for client in clients:
        # Get current driver (may restart if port rotation needed)
        driver = get_driver()
        
        # Handle both single phone number (string) and multiple phone numbers (list)
        phone_numbers = client.get("phone_number", client.get("phone_numbers", []))
        if isinstance(phone_numbers, str):
            phone_numbers = [phone_numbers]  # Convert single number to list
        elif not isinstance(phone_numbers, list):
            print(f"[-] Invalid phone number format for client: {client}")
            continue
            
        if not phone_numbers:
            print(f"[-] No phone numbers found for client: {client}")
            continue
            
        # Use the first phone number as the primary key for tracking
        primary_phone = phone_numbers[0]
        
        matched_listings[primary_phone] = matched_listings.get(primary_phone, [])
        visited_count = len(visited_links.get(primary_phone, []))
        print(f"\n[*] Processing client with {len(phone_numbers)} phone number(s): {', '.join(phone_numbers)}")
        print(f"[*] Primary tracking phone: {primary_phone} (visited {visited_count} item IDs previously)")
        driver.get("https://www.facebook.com/marketplace")
        human_sleep(2, 4)

        # ZIP code change logic (keeping your existing code)
        try:
            location_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and .//span[contains(., '·')]]"))
            )
            location_btn.click()
            print("[+] Clicked location selector")
            human_sleep(1, 2)

            zip_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@role='combobox' and @aria-label='Location']"))
            )
            zip_input.click()
            human_sleep(0.3, 0.8)
            zip_input.send_keys(Keys.CONTROL + "a")
            zip_input.send_keys(Keys.DELETE)
            human_sleep(0.4, 0.9)
            zip_input.send_keys(client["location"])
            print(f"[+] Entered ZIP code: {client['location']}")
            human_sleep(1, 2)

            first_suggestion = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "(//div[@role='option'])[1]"))
            )
            first_suggestion.click()
            print("[+] Clicked first suggestion")
            human_sleep(0.8, 1.5)

            apply_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Apply']"))
            )
            apply_button.click()
            print("[+] Clicked 'Apply' to confirm ZIP")

            human_sleep(1.5, 2.5)
        except Exception as e:
            print(f"[-] Failed to update ZIP code: {e}")

        # Search
        search_input = driver.find_element(By.XPATH, "//input[@placeholder='Search Marketplace']")
        search_input.clear()
        human_sleep(0.5, 1.2)
        search_input.send_keys(client["make_model"])
        human_sleep(0.8, 1.5)
        search_input.send_keys("\n")
        human_sleep(3, 5)  # Wait for search results to load
        
        # Try to apply "Date listed" filter with error handling
        try:
            # Try multiple possible XPaths for the Date listed button
            date_listed_button = None
            possible_xpaths = [
                "//span[text()='Date listed']",
                "//span[contains(text(), 'Date listed')]",
                "//div[contains(text(), 'Date listed')]",
                "//button[contains(text(), 'Date listed')]",
                "//span[text()='Sort']",  # Sometimes it's labeled as Sort
                "//div[@role='button' and contains(., 'Date')]"
            ]
            
            for xpath in possible_xpaths:
                try:
                    date_listed_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    date_listed_button.click()
                    print(f"[+] Clicked date filter using xpath: {xpath}")
                    human_sleep(0.8, 1.5)
                    break
                except:
                    continue
            
            if date_listed_button:
                try:
                    # Try multiple possible XPaths for Last 24 hours
                    last_24_xpaths = [
                        "//span[text()='Last 24 hours']",
                        "//span[contains(text(), '24 hours')]",
                        "//div[contains(text(), '24 hours')]",
                        "//span[text()='Today']"
                    ]
                    
                    for xpath in last_24_xpaths:
                        try:
                            Last_24hrs_button = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, xpath))
                            )
                            Last_24hrs_button.click()
                            print(f"[+] Applied time filter using xpath: {xpath}")
                            human_sleep(0.8, 1.5)
                            break
                        except:
                            continue
                    else:
                        print("[-] Could not find 'Last 24 hours' option")
                        
                except Exception as e:
                    print(f"[-] Failed to apply time filter: {e}")
            else:
                print("[-] Could not find any date filter button")
                
        except Exception as e:
            print(f"[-] Failed to find date filter: {e}")
            print("[*] Continuing without date filter...")
            
        human_sleep(2, 4)
        
        # Generate random search time between 3-4 minutes (180-240 seconds)
        search_time_limit = random.randint(120, 150)
        print(f"[+] Search time limit set to {search_time_limit} seconds ({search_time_limit/60:.1f} minutes)")
        
        start_time = time.time()
        SCROLL_PAUSE = random.uniform(2.5, 4.5)  # Random scroll pause
        matchFound = False
        while time.time() - start_time < search_time_limit and not matchFound:
            listings = driver.find_elements(By.XPATH, "//a[contains(@href, '/marketplace/item')]")
            human_sleep(1.5, 3)
            for item in listings:
                if time.time() - start_time > search_time_limit:
                    print("[*] Time limit reached, stopping search.")
                    break
                human_sleep(2.5, 4.5)  # Random delay between processing items
                href= item.get_attribute("href")
                title = item.text
                
                # Extract item ID from the URL
                item_id = extract_item_id(href)
                
                print("\n" + "="*50)
                print(f"[+] Processing listing: {title} ({href})")
                print(f"[+] Item ID: {item_id}")
                
                if not href or not title or not item_id:
                    print("[-] Missing href, title, or item ID - skipping")
                    continue

                # Check if this item ID has been visited for this client
                phone_make= primary_phone + client.get("make_model", "")
                if is_item_visited(item_id, phone_make):
                    print(f"[-] Item ID {item_id} already visited for this client, skipping")
                    continue

                # Mark item ID as visited for this client (do this early to avoid revisiting if there's an error)
                mark_item_visited(item_id, phone_make)

                # Open listing in new tab with improved method
                try:
                    # Store original window count
                    original_windows = len(driver.window_handles)
                    
                    # Try multiple methods to open new tab
                    success = False
                    
                    # Method 1: JavaScript window.open
                    try:
                        driver.execute_script("window.open(arguments[0]);", href)
                        human_sleep(0.8, 1.5)
                        if len(driver.window_handles) > original_windows:
                            success = True
                            print("[+] Opened new tab using window.open()")
                    except Exception as e:
                        print(f"[-] window.open() failed: {e}")
                    
                    # Method 2: Ctrl+Click simulation
                    if not success:
                        try:
                            driver.execute_script("""
                                var link = document.createElement('a');
                                link.href = arguments[0];
                                link.target = '_blank';
                                link.rel = 'noopener noreferrer';
                                document.body.appendChild(link);
                                link.click();
                                document.body.removeChild(link);
                            """, href)
                            human_sleep(0.8, 1.5)
                            if len(driver.window_handles) > original_windows:
                                success = True
                                print("[+] Opened new tab using link simulation")
                        except Exception as e:
                            print(f"[-] Link simulation failed: {e}")
                    
                    # Method 3: Keys combination
                    if not success:
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            # Find the listing link element and Ctrl+click it
                            link_element = driver.find_element(By.XPATH, f"//a[@href='{href}']")
                            ActionChains(driver).key_down(Keys.CONTROL).click(link_element).key_up(Keys.CONTROL).perform()
                            human_sleep(0.8, 1.5)
                            if len(driver.window_handles) > original_windows:
                                success = True
                                print("[+] Opened new tab using Ctrl+click")
                        except Exception as e:
                            print(f"[-] Ctrl+click failed: {e}")
                    
                    # Check if any method worked
                    if not success or len(driver.window_handles) <= original_windows:
                        print("[-] All tab opening methods failed, skipping listing")
                        continue
                    
                    # Switch to the new tab
                    driver.switch_to.window(driver.window_handles[-1])  # Switch to last opened tab
                    human_sleep(1.5, 2.5)
                    print(f"[+] Successfully switched to new tab")
                    
                except Exception as e:
                    print(f"[-] Error opening new tab: {e}")
                    continue

                try:
                    # Check if listing was posted within hours (not days/weeks/months ago)
                    try:
                        time_posted = driver.find_element(
    By.XPATH,
    "//span[contains(text(), 'hours ago') or contains(text(), 'hour ago') or contains(text(), 'minutes ago') or contains(text(), 'minute ago')]"
)
                        print(f"[+] Listing posted: {time_posted.text}")
                    except:
                        print("[-] Listing not posted within hours - skipping")
                        try:
                            driver.close()
                            if len(driver.window_handles) > 0:
                                driver.switch_to.window(driver.window_handles[0])
                        except Exception as close_e:
                            print(f"[-] Error closing tab: {close_e}")
                        continue
                    
                    # Extract price
                    try:
                        price_element = driver.find_element(By.XPATH, "//span[contains(text(), '$')]").text
                        price = extract_price(price_element)
                    except Exception as e:
                        price_element = driver.find_element(By.XPATH, "/html/body/div[1]/div/div[1]/div/div[5]/div/div/div[3]/div[2]/div/div/div[2]/div/div[2]/div/div[2]/div[1]/div[1]/div[2]/div/span").text
                        price = extract_price(price_element)
                    print(f"[+] Price: ${price:,}" if price else "[-] Price not found")

                    # Extract all vehicle details
                    vehicle_details = extract_vehicle_details(driver)
                    vehicle_details['title'] = title
                    vehicle_details['href'] = href
                    # Print summary
                
                    print(f"VEHICLE SUMMARY:")
                    print(f"Price: ${price:,}" if price else "Price: Not found")
                    print(f"Miles: {vehicle_details['miles']:,}" if vehicle_details['miles'] else "Miles: Not found")
                    print(f"Transmission: {vehicle_details['transmission']}" if vehicle_details['transmission'] else "Transmission: Not found")
                    print(f"Colors: {vehicle_details['exterior_color']} / {vehicle_details['interior_color']}" if vehicle_details['exterior_color'] else "Colors: Not found")
                    print(f"Fuel: {vehicle_details['fuel_type']}" if vehicle_details['fuel_type'] else "Fuel: Not found")
                    print(f"Owners: {vehicle_details['owners']}" if vehicle_details['owners'] else "Owners: Not found")
                    print(f"Paid off: {vehicle_details['paid_off']}")
                    print(f"History: {vehicle_details['history_description']}")
                    
                    # Apply filters
                    miles = vehicle_details['miles']
                    
                    # Check if client has miles requirements
                    has_miles_requirements = client.get("min_miles") is not None and client.get("max_miles") is not None
                    
                    if (
                        price is not None
                        and client["min_price"] <= price <= client["max_price"] 
                        and (not has_miles_requirements or miles is None or (client["min_miles"] <= miles <= client["max_miles"]))
                        and matches_filters(vehicle_details, client)
                        and matches_required_fields(vehicle_details, client)
                    ):
                        
                        if title in matched_listings[primary_phone]:
                            print(f"[-] Listing already matched for this client: {title}")
                        else:
                            print(f"[+] MATCH FOUND! Listing meets all criteria.")
                            matched_listings[primary_phone].append(title)
                            save_matched_listings(matched_listings)  # Save to file immediately
                            matchFound = True
                            
                            # Send SMS to all phone numbers for this client
                            sms_message = f"New vehicle found according to your desired requirements: {title} ({href}). Better check it out!"
                            for phone_num in phone_numbers:
                                try:
                                    send_sms(sms_message, phone_num)
                                    print(f"[+] SMS sent to {phone_num}")
                                except Exception as sms_error:
                                    print(f"[-] Failed to send SMS to {phone_num}: {sms_error}")
                            
                            human_sleep(1.5, 2)  # Give time for SMS to send
                            try:
                                driver.close()
                                if len(driver.window_handles) > 0:
                                    driver.switch_to.window(driver.window_handles[0])
                            except Exception as close_e:
                                print(f"[-] Error closing tab: {close_e}")
                            break  # move to next client
                    else:
                        print(f"[-] Listing doesn't meet criteria")
                    print("="*50 + "\n\n\n")
                except Exception as e:
                    print(f"[-] Error processing listing: {e}")
                    continue

                try:
                    driver.close()
                    if len(driver.window_handles) > 0:
                        driver.switch_to.window(driver.window_handles[0])
                except Exception as close_e:
                    print(f"[-] Error closing tab: {close_e}")
                human_sleep(2.5, 4.5)  # Random delay before processing next item
                
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            human_sleep(SCROLL_PAUSE, SCROLL_PAUSE + 1.5)
        print("[*] Finished processing listings for this client.\n\n")
        human_sleep(3, 6)  # Rest between clients
    # Close all extra tabs except the first one
    try:
        main_tab = driver.window_handles[0] if len(driver.window_handles) > 0 else None
        if main_tab:
            for handle in driver.window_handles:
                if handle != main_tab:
                    try:
                        driver.switch_to.window(handle)
                        driver.close()
                    except Exception as e:
                        print(f"[-] Failed to close tab: {e}")

            # Return to main tab
            try:
                driver.switch_to.window(main_tab)
                print("[*] Cleaned up all extra tabs.")
            except Exception as e:
                print(f"[-] Error returning to main tab: {e}")
    except Exception as e:
        print(f"[-] Error during tab cleanup: {e}")
