import streamlit as st
import pandas as pd
import openai
import re
import time
from io import StringIO
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager
import logging
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Email Extractor & Automation Agent",
    page_icon="📧",
    layout="wide"
)

# Initialize session state
if 'extracted_emails' not in st.session_state:
    st.session_state.extracted_emails = []
if 'automation_logs' not in st.session_state:
    st.session_state.automation_logs = []
if 'automation_running' not in st.session_state:
    st.session_state.automation_running = False

st.title("📧 Email Extractor & Automation Agent")
st.markdown("Upload a CSV file, extract emails, and automate form submissions")

# Sidebar for API key input
with st.sidebar:
    st.header("🔑 Configuration")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        help="Enter your OpenAI API key to extract emails from the CSV file"
    )
    
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("""
    1. Enter your OpenAI API key in the sidebar
    2. Upload a CSV file
    3. Click 'Extract Emails' to process
    4. Download the results as CSV
    """)

# Main content area
uploaded_file = st.file_uploader(
    "Choose a CSV file",
    type=['csv'],
    help="Upload a CSV file containing data with email addresses"
)

if uploaded_file is not None:
    # Read the CSV file
    try:
        df = pd.read_csv(uploaded_file)
        st.success(f"✅ File uploaded successfully! ({len(df)} rows)")
        
        # Display preview of the uploaded file
        with st.expander("📋 Preview of uploaded CSV", expanded=False):
            st.dataframe(df.head(10))
        
        # Extract emails button
        if st.button("🔍 Extract Emails", type="primary"):
            if not api_key:
                st.error("❌ Please enter your OpenAI API key in the sidebar")
            else:
                with st.spinner("🔄 Extracting emails using OpenAI API..."):
                    try:
                        # Set OpenAI API key
                        openai.api_key = api_key
                        client = openai.OpenAI(api_key=api_key)
                        
                        # Convert DataFrame to string for analysis
                        csv_string = df.to_string()
                        
                        # Use OpenAI to extract emails
                        prompt = f"""Analyze the following CSV data and extract all email addresses. 
Return only the email addresses, one per line, without any additional text or explanation.
If no emails are found, return "No emails found".

CSV Data:
{csv_string[:4000]}"""  # Limit to avoid token limits
                        
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are an expert at extracting email addresses from text data. Return only email addresses, one per line."},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.1,
                            max_tokens=1000
                        )
                        
                        # Parse the response
                        extracted_text = response.choices[0].message.content.strip()
                        
                        # Also use regex as a fallback to find emails in the CSV
                        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                        regex_emails = set(re.findall(email_pattern, csv_string, re.IGNORECASE))
                        
                        # Combine OpenAI results with regex results
                        ai_emails = [line.strip() for line in extracted_text.split('\n') 
                                    if '@' in line and 'No emails found' not in line]
                        
                        # Combine and deduplicate
                        all_emails = list(set(ai_emails + list(regex_emails)))
                        all_emails = [email for email in all_emails if email and '@' in email]
                        
                        if all_emails:
                            # Store emails in session state
                            st.session_state.extracted_emails = sorted(all_emails)
                            
                            st.success(f"✅ Found {len(all_emails)} unique email address(es)")
                            
                            # Display emails
                            st.subheader("📬 Extracted Emails")
                            emails_df = pd.DataFrame({'Email': sorted(all_emails)})
                            st.dataframe(emails_df, use_container_width=True)
                            
                            # Download button
                            csv_download = emails_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Emails as CSV",
                                data=csv_download,
                                file_name="extracted_emails.csv",
                                mime="text/csv"
                            )
                            
                            # Statistics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Emails", len(all_emails))
                            with col2:
                                st.metric("Unique Domains", len(set([email.split('@')[1] for email in all_emails if '@' in email])))
                            with col3:
                                st.metric("Source Rows", len(df))
                        else:
                            st.warning("⚠️ No email addresses found in the CSV file")
                            st.session_state.extracted_emails = []
                    
                    except openai.AuthenticationError:
                        st.error("❌ Invalid API key. Please check your OpenAI API key.")
                    except openai.RateLimitError:
                        st.error("❌ Rate limit exceeded. Please try again later.")
                    except openai.APIError as e:
                        st.error(f"❌ OpenAI API Error: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
    
    except Exception as e:
        st.error(f"❌ Error reading CSV file: {str(e)}")
        st.info("Please make sure you uploaded a valid CSV file.")

else:
    st.info("👆 Please upload a CSV file to get started")

# Automation Agent Section
if st.session_state.extracted_emails:
    st.markdown("---")
    st.header("🤖 Automation Agent")
    st.markdown("Automatically submit extracted emails to a web form")
    
    # Automation Configuration
    with st.expander("⚙️ Automation Settings", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            target_url = st.text_input(
                "🌐 Target URL",
                placeholder="https://example.com/signup",
                help="Enter the URL of the page with the signup form"
            )
            
            delay_between_submissions = st.number_input(
                "⏱️ Delay between submissions (seconds)",
                min_value=1,
                max_value=60,
                value=3,
                help="Wait time between each email submission"
            )
        
        with col2:
            headless_mode = st.checkbox(
                "🫥 Run in headless mode",
                value=False,
                help="Run browser in background (no visible window)"
            )
            
            timeout_seconds = st.number_input(
                "⏰ Page timeout (seconds)",
                min_value=5,
                max_value=60,
                value=30,
                help="Maximum time to wait for page elements"
            )
    
    # Custom Selectors
    with st.expander("🎯 Custom Element Selectors (Optional)", expanded=False):
        st.markdown("**Leave empty to use default selectors**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            custom_email_selector = st.text_input(
                "Email Input Selector (CSS or XPath)",
                placeholder='input[type="email"]',
                help="CSS selector or XPath for email input field"
            )
        
        with col2:
            custom_submit_selector = st.text_input(
                "Submit Button Selector (CSS or XPath)",
                placeholder='//button[contains(text(), "Sign up")]',
                help="CSS selector or XPath for submit button"
            )
    
    # Automation Functions
    def find_element_by_selectors(driver, selectors):
        """Try multiple selectors to find an element (supports both CSS and XPath)"""
        for selector in selectors:
            if not selector:
                continue
            try:
                # Try XPath first if it starts with // or .//
                if selector.startswith('//') or selector.startswith('.//') or selector.startswith('('):
                    try:
                        element = driver.find_element(By.XPATH, selector)
                        if element.is_displayed():
                            return element, selector, 'xpath'
                    except (NoSuchElementException, ElementNotInteractableException):
                        pass
                else:
                    # Try CSS selector
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        if element.is_displayed():
                            return element, selector, 'css'
                    except (NoSuchElementException, ElementNotInteractableException):
                        pass
            except Exception:
                continue
        return None, None, None
    
    def is_driver_valid(driver):
        """Check if the driver session is still valid"""
        try:
            if driver is None:
                return False
            # Try to get current URL to check if session is alive
            driver.current_url
            return True
        except:
            return False
    
    def create_driver(timeout, headless):
        """Create a new Chrome driver instance"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(timeout)
        return driver
    
    def process_email_automation(email, url, email_selectors, submit_selectors, delay, timeout, headless, driver=None, is_first_email=False):
        """Process a single email through the automation workflow"""
        log_entry = {
            'email': email,
            'status': 'processing',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'details': []
        }
        
        driver_created_here = False
        try:
            # Check if driver is valid, if not create a new one
            if not is_driver_valid(driver):
                log_entry['details'].append("🔄 Creating new browser session...")
                driver = create_driver(timeout, headless)
                driver_created_here = True
                log_entry['details'].append(f"✅ Browser initialized")
                is_first_email = True  # Force navigation if driver was recreated
            
            # Navigate to URL (or refresh if not first email)
            try:
                if is_first_email:
                    log_entry['details'].append(f"🌐 Navigating to: {url}")
                    driver.get(url)
                else:
                    log_entry['details'].append(f"🔄 Refreshing page...")
                    try:
                        driver.refresh()
                    except Exception as refresh_error:
                        # If refresh fails, try navigating again
                        log_entry['details'].append(f"⚠️ Refresh failed, navigating to URL instead: {str(refresh_error)}")
                        driver.get(url)
            except Exception as e:
                log_entry['details'].append(f"⚠️ Navigation error: {str(e)}, attempting to recreate browser...")
                # If navigation fails, try recreating driver
                try:
                    if driver and is_driver_valid(driver):
                        driver.quit()
                except:
                    pass
                driver = create_driver(timeout, headless)
                driver_created_here = True
                log_entry['details'].append("🔄 Recreated browser after navigation failure")
                try:
                    driver.get(url)
                except Exception as nav_error:
                    log_entry['status'] = 'failed'
                    log_entry['details'].append(f"❌ Failed to navigate after recreation: {str(nav_error)}")
                    return log_entry, driver
            
            time.sleep(2)  # Wait for page to load
            
            # Find email input field
            log_entry['details'].append("🔍 Searching for email input field...")
            email_element, used_selector, selector_type = find_element_by_selectors(driver, email_selectors)
            
            if not email_element:
                log_entry['status'] = 'failed'
                log_entry['details'].append("❌ Email input field not found with any selector")
                return log_entry, driver
            
            log_entry['details'].append(f"✅ Found email field using {selector_type.upper()}: {used_selector}")
            
            # Clear and enter email
            try:
                email_element.clear()
                time.sleep(0.2)
                email_element.send_keys(email)
                log_entry['details'].append(f"✍️ Entered email: {email}")
                time.sleep(0.5)
            except Exception as e:
                log_entry['status'] = 'failed'
                log_entry['details'].append(f"❌ Failed to enter email: {str(e)}")
                return log_entry, driver
            
            # Find and click submit button
            log_entry['details'].append("🔍 Searching for submit button...")
            submit_element, used_submit_selector, submit_selector_type = find_element_by_selectors(driver, submit_selectors)
            
            if not submit_element:
                log_entry['status'] = 'failed'
                log_entry['details'].append("❌ Submit button not found with any selector")
                return log_entry, driver
            
            log_entry['details'].append(f"✅ Found submit button using {submit_selector_type.upper()}: {used_submit_selector}")
            
            # Scroll to element and click
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_element)
                time.sleep(0.5)
                submit_element.click()
                log_entry['details'].append("🖱️ Clicked submit button")
            except Exception as e:
                log_entry['status'] = 'failed'
                log_entry['details'].append(f"❌ Failed to click submit button: {str(e)}")
                return log_entry, driver
            
            # Wait for submission to complete
            time.sleep(delay)
            log_entry['details'].append(f"⏳ Waited {delay} seconds for submission")
            
            log_entry['status'] = 'success'
            log_entry['details'].append("✅ Submission completed successfully")
            
        except TimeoutException as e:
            log_entry['status'] = 'failed'
            log_entry['details'].append(f"❌ Timeout: Page took too long to load - {str(e)}")
            # Don't close driver on timeout, let it be reused
        except Exception as e:
            log_entry['status'] = 'failed'
            log_entry['details'].append(f"❌ Error: {str(e)}")
            # If driver was created here and there's an error, we might need to recreate it
            if driver_created_here:
                try:
                    if not is_driver_valid(driver):
                        driver = None  # Signal that driver needs to be recreated
                except:
                    driver = None
        
        # Never close the driver here - let the calling function manage it
        return log_entry, driver
    
    def run_automation():
        """Run automation for all emails"""
        if not target_url or not target_url.startswith(('http://', 'https://')):
            st.error("❌ Please enter a valid URL starting with http:// or https://")
            return
        
        if not st.session_state.extracted_emails:
            st.error("❌ No emails to process. Please extract emails first.")
            return
        
        st.session_state.automation_running = True
        st.session_state.automation_logs = []
        
        # Prepare selectors
        default_email_selectors = [
            'input[placeholder="Your email"][type="text"]',
            'input[type="email"]',
            'input[placeholder*="email"]',
            'input[placeholder*="Email"]',
            'input[name*="email"]',
            'input[name*="Email"]',
            'input[id*="email"]',
            'input[id*="Email"]',
            'input[placeholder*="e-mail"]',
            'input[name*="e-mail"]'
        ]
        
        default_submit_selectors = [
            "//button[contains(text(), 'Sign up for free')]",
            "//button[contains(text(), 'Sign up')]",
            "//input[@type='submit']",
            "//button[@type='submit']",
            "//button[contains(@class, 'submit')]",
            "//a[contains(text(), 'Sign up')]"
        ]
        
        email_selectors = [custom_email_selector] + default_email_selectors if custom_email_selector else default_email_selectors
        submit_selectors = [custom_submit_selector] + default_submit_selectors if custom_submit_selector else default_submit_selectors
        
        # Process each email
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_container = st.container()
        
        total_emails = len(st.session_state.extracted_emails)
        success_count = 0
        failed_count = 0
        driver = None
        
        try:
            for idx, email in enumerate(st.session_state.extracted_emails):
                if not st.session_state.automation_running:
                    break
                
                status_text.text(f"Processing {idx + 1}/{total_emails}: {email}")
                progress_bar.progress((idx + 1) / total_emails)
                
                is_first = (idx == 0 or driver is None)
                
                # Process email and get updated driver
                log_entry, driver = process_email_automation(
                    email, target_url, email_selectors, submit_selectors,
                    delay_between_submissions, timeout_seconds, headless_mode,
                    driver=driver, is_first_email=is_first
                )
                
                st.session_state.automation_logs.append(log_entry)
                
                if log_entry['status'] == 'success':
                    success_count += 1
                else:
                    failed_count += 1
                
                # Display logs in real-time
                with log_container:
                    st.markdown(f"**Email {idx + 1}: {email}**")
                    if log_entry['status'] == 'success':
                        st.success("✅ Success")
                    else:
                        st.error("❌ Failed")
                    for detail in log_entry['details']:
                        st.text(f"  {detail}")
                    st.markdown("---")
                
                # Small delay between emails to ensure page is ready
                if idx < total_emails - 1:  # Don't wait after last email
                    time.sleep(1)
                    
        except Exception as e:
            st.error(f"❌ Fatal error in automation loop: {str(e)}")
        finally:
            # Close browser if still open (only at the very end)
            if driver and is_driver_valid(driver):
                try:
                    driver.quit()
                    st.info("🔒 Browser closed after processing all emails")
                except Exception as e:
                    pass
        
        st.session_state.automation_running = False
        progress_bar.empty()
        
        # Final summary
        st.success(f"✅ Automation completed!")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Processed", total_emails)
        with col2:
            st.metric("✅ Successful", success_count)
        with col3:
            st.metric("❌ Failed", failed_count)
    
    # Automation Controls
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if st.button("🚀 Start Automation", type="primary", disabled=st.session_state.automation_running):
            run_automation()
    
    with col2:
        if st.button("⏹️ Stop Automation", disabled=not st.session_state.automation_running):
            st.session_state.automation_running = False
            st.warning("⏹️ Automation stopped by user")
            st.rerun()
    
    with col3:
        if st.button("📋 View Logs"):
            if st.session_state.automation_logs:
                st.subheader("📋 Automation Logs")
                for log in st.session_state.automation_logs:
                    with st.expander(f"{log['email']} - {log['status'].upper()}", expanded=False):
                        st.text(f"Timestamp: {log['timestamp']}")
                        for detail in log['details']:
                            st.text(detail)
            else:
                st.info("No logs available. Run automation first.")

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>Made with Streamlit, OpenAI & Selenium</div>",
    unsafe_allow_html=True
)

