# Pre-requisites:
- Fork the repository 
- In the streamlit_app.py change GITHUB_REPO to your repo e.g. GITHUB_REPO = "mshaikh786/aimcr-reviews"
- Create a Github Personal Access token (classic) so that the app can communicate with your repo
- Create and activate the conda environment. Use the requirements.txt for software

# Start the application
`streamlit run streamlit_app.py`

# Saving artifacts
Make sure to save the artifact. Clicking the button "Save Draft" will checkpoint the status of the draft along with git push the draft in your repository.

# Submission
Submitting the draft at the end will move it from draft to a submission folder in the form of a JSON. 

# Create PDF
The `json_to_pdf.py` script creates a PDF from JSON
`json_to_pdf.py` submission/<filename.json> my.pdf`
