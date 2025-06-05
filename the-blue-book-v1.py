import streamlit as st
import pdfplumber
import requests
import json
import re
from datetime import datetime

# Streamlit app title
st.title("Blue Book PDF Analyzer")

# Input for Gemini API key
api_key = st.text_input("Enter your Google Gemini API Key", type="password")

# File uploader for multiple PDFs
uploaded_files = st.file_uploader("Upload Blue Book PDFs (Addendum, Specs, Plans)", accept_multiple_files=True, type=["pdf"])

# Function to extract text from PDFs
def extract_pdf_text(uploaded_files):
    pdf_texts = []
    page_mappings = []
    for uploaded_file in uploaded_files:
        with pdfplumber.open(uploaded_file) as pdf:
            text = ""
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text += f"\n[Page {page_num}]\n{page_text}"
                    page_mappings.append((uploaded_file.name, page_num, page_text))
            pdf_texts.append((uploaded_file.name, text))
    return pdf_texts, page_mappings

# Function to call Gemini API
def call_gemini_api(api_key, prompt):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    try:
        response = requests.post(f"{url}?key={api_key}", headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    except Exception as e:
        st.error(f"Error calling Gemini API: {str(e)}")
        return None

# Function to parse Gemini API response
def parse_gemini_response(response, page_mappings):
    if not response:
        return None
    
    # Initialize result dictionary
    result = {
        "contractor": "",
        "architect": "",
        "designer": "",
        "client": "",
        "trades": {},
        "project_start_date": "",
        "project_end_date": ""
    }
    
    # Simple regex patterns for extraction
    patterns = {
        "contractor": r"(?:Contractor|Builder):?\s*([A-Za-z\s]+)",
        "architect": r"Architect:?\s*([A-Za-z\s]+)",
        "designer": r"Designer:?\s*([A-Za-z\s]+)",
        "client": r"(?:Client|Owner):?\s*([A-Za-z\s]+)",
        "start_date": r"(?:Start Date|Commencement):?\s*(\d{1,2}/\d{1,2}/\d{4})",
        "end_date": r"(?:End Date|Completion):?\s*(\d{1,2}/\d{1,2}/\d{4})"
    }
    
    # Extract basic entities
    for key, pattern in patterns.items():
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()
    
    # Extract trades and resources with page numbers
    trades_section = re.findall(r"(Trade:.*?)(?=(Trade:|$))", response, re.DOTALL)
    for trade in trades_section:
        trade_name_match = re.search(r"Trade:\s*([^\n]+)", trade)
        if trade_name_match:
            trade_name = trade_name_match.group(1).strip()
            resources = []
            page_numbers = []
            
            # Find resources
            resource_matches = re.findall(r"Resources:?\s*([^\n]+)", trade)
            for res in resource_matches:
                resources.append(res.strip())
            
            # Find page numbers from page_mappings
            for file_name, page_num, page_text in page_mappings:
                if trade_name.lower() in page_text.lower():
                    page_numbers.append(f"{file_name}: Page {page_num}")
            
            result["trades"][trade_name] = {
                "resources": resources,
                "pages": page_numbers
            }
    
    return result

# Process uploaded PDFs
if uploaded_files and api_key:
    if st.button("Analyze PDFs"):
        with st.spinner("Processing PDFs..."):
            # Extract text from PDFs
            pdf_texts, page_mappings = extract_pdf_text(uploaded_files)
            
            # Combine all PDF text for analysis
            combined_text = "\n".join([text for _, text in pdf_texts])
            
            # Create prompt for Gemini API
            prompt = f"""Analyze the following construction-related PDF content and extract:
1. Contractor name
2. Architect name
3. Designer name
4. Client name
5. Construction elements/resources for each trade
6. Page numbers where each trade's specs/plans appear
7. Project start date
8. Project end date

Provide the output in a structured format. Here is the PDF content:\n{combined_text}"""
            
            # Call Gemini API
            gemini_response = call_gemini_api(api_key, prompt)
            
            if gemini_response:
                # Parse the response
                result = parse_gemini_response(gemini_response, page_mappings)
                
                if result:
                    # Display results
                    st.subheader("Analysis Results")
                    st.write(f"**Contractor**: {result['contractor']}")
                    st.write(f"**Architect**: {result['architect']}")
                    st.write(f"**Designer**: {result['designer']}")
                    st.write(f"**Client**: {result['client']}")
                    st.write(f"**Project Start Date**: {result['project_start_date']}")
                    st.write(f"**Project End Date**: {result['project_end_date']}")
                    
                    st.subheader("Trades and Resources")
                    for trade, details in result["trades"].items():
                        st.write(f"**Trade**: {trade}")
                        st.write(f"**Resources**: {', '.join(details['resources'])}")
                        st.write(f"**Page Numbers**: {', '.join(details['pages'])}")
                        st.write("---")
                else:
                    st.error("Could not parse the analysis results.")
            else:
                st.error("Failed to get a valid response from the Gemini API.")
else:
    st.info("Please upload PDF files and provide a valid Gemini API key.")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit and Google Gemini API")
