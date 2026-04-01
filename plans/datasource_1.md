Since your team is building scrapers and looking to distribute the workload, bypassing the web interfaces and downloading the raw database files is the most scalable method.

Here is the step-by-step documentation for both the IPEDS and NSF GSS options.

Option 1: IPEDS Complete Data Files (The Developer's Route)
Because IPEDS covers every degree-granting institution in the country, this dataset is massive. The most efficient way to get your exact mapping is to download the raw CSVs and merge them programmatically.

Step 1: Download the Raw Data

Navigate to the IPEDS Use the Data portal.

Under the "Download IPEDS Data" section, click on Complete Data Files.

Select the most recent data year available from the dropdown (e.g., 2023 or 2024).

You need to download two specific CSV datasets (look for the .zip containing the CSVs):

Institutional Characteristics (Directory Information): The file will be named starting with HD (e.g., HD2023). This contains the master list of universities, their names, states, and their unique UNITID.

Completions: The file will be named starting with C and ending with _A (e.g., C2023_A). This contains the massive list of every degree awarded by every university, broken down by specific discipline.

Download the accompanying Dictionary files for both datasets. These provide the translation keys for the column headers.

Step 2: Filter and Merge the CSVs
Once extracted, you will apply the following filtering logic (easily done via Python/Pandas or a SQL database) to create your master list:

Load the Completions CSV.

Filter by PhDs Only: Keep only the rows where the AWLEVEL (Award Level) column equals 17. In the IPEDS dictionary, 17 strictly designates "Doctor's degree - research/scholarship."

Filter by STEM Disciplines: IPEDS classifies departments using CIP (Classification of Instructional Programs) codes. Filter the CIPCODE column to keep only rows starting with the primary STEM 2-digit families:

11.xxxx (Computer and Information Sciences)

14.xxxx (Engineering)

26.xxxx (Biological and Biomedical Sciences)

27.xxxx (Mathematics and Statistics)

40.xxxx (Physical Sciences)

Merge the Datasets: Load the Institutional Characteristics CSV (HD) and merge it with your filtered Completions data, using the UNITID column as the relational key.

Output: You will now have a clean dataset mapping State -> University Name -> Specific STEM PhD Discipline.