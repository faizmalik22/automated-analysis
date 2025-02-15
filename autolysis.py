# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "matplotlib",
#   "seaborn",
#   "scikit-learn",
#   "tenacity",
#   "requests",
#   "chardet",
# ]
# ///

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import json
import re
import requests
import time
from datetime import datetime
import base64
import chardet
from sklearn.impute import SimpleImputer
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from tenacity import retry, stop_after_attempt, wait_fixed



# Check if environment variable is set for AI Proxy Token
if "AIPROXY_TOKEN" not in os.environ:
    print("Error: Please set the AIPROXY_TOKEN environment variable.")
    sys.exit(1)

AIPROXY_TOKEN = os.environ["AIPROXY_TOKEN"]
AI_PROXY_URL = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def call_llm_api(content):
    """ Function to call GPT-4o-Mini via AI Proxy API with retry logic."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AIPROXY_TOKEN}"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": content}]
    }
    response = requests.post(AI_PROXY_URL, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        print(f"Error calling API: {response.status_code}\n{response.text}")
        sys.exit(1)


def analyze_missing_values(df):
    """ Analyze and report missing values in the dataset. """
    missing_values = df.isnull().sum()
    print("Missing Values:\n", missing_values)
    return missing_values

def detect_outliers(df):
    """ Detect outliers in numerical columns using the IQR method. """
    outlier_summary = {}
    num_cols = df.select_dtypes(include='number').columns.tolist()
    for col in num_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))]
        outlier_summary[col] = len(outliers)
    print("Outlier Summary:", outlier_summary)
    return outlier_summary

def correlation_analysis(df):
    """ Compute and visualize correlation matrix for numerical features. """
    num_cols = df.select_dtypes(include='number').columns
    if len(num_cols) > 1:
        corr = df[num_cols].corr()
        plt.figure(figsize=(8, 6))
        sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f")
        plt.title("Correlation Matrix")
        corr_file = "correlation_matrix.png"
        plt.savefig(corr_file)
        plt.close()
        print("Correlation analysis complete.")
        return corr_file
    return None

def generate_visualizations(df):
    """ Generate visualizations based on dataset statistics. """
    images = []
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # Histogram for numerical columns
    num_cols = df.select_dtypes(include='number').columns
    for col in num_cols[:3]:
        plt.figure(figsize=(8, 6))
        df[col].plot(kind='hist', bins=20, color='skyblue', edgecolor='black')
        plt.title(f"Distribution of {col}")
        plt.xlabel(col)
        plt.ylabel("Frequency")
        hist_file = f"{col}_histogram.png"
        plt.savefig(hist_file, dpi=100)
        images.append(hist_file)
        plt.close()
    
    # Boxplot of all numerical columns
    if len(num_cols) > 0:
        plt.figure(figsize=(10, 6))
        df[num_cols].boxplot()
        plt.title("Box Plot of Numerical Columns")
        boxplot_file = "boxplot.png"
        plt.savefig(boxplot_file, dpi=100)
        images.append(boxplot_file)
        plt.close()
    
    return images

def get_self_analysis_summary(missing_values, outlier_summary):
    text = f"""
    You are an expert data scientist. Give me summary of this analysis.

    Given below is the analysys:
    Missing Values: {missing_values}
    Outlier Summary: {outlier_summary}
    
    """
    prompt_content = create_prompt_content(text, images_path=[])
    response = call_llm_api(prompt_content)
    return response


def encode_image(image_path):
    """Encodes image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def create_prompt_content(text, images_path):
    """Creates the prompt content with multiple base64 encoded images."""
    content = [{"type": "text", "text": text}]  # Starting with the text part
    if len(images_path) > 0 :
        for image_path in images_path:
            base64_image = encode_image(image_path)  # Encode the current image
            image_content = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "low"  # Low resolution for all images, adjust if necessary
                },
            }
            content.append(image_content)  # Add each image to the content

    return content

def convert_data_types(data_types):
    """Helper function to convert pandas data types to Python native types for JSON serialization."""
    return {key: str(value) for key, value in data_types.items()}


def interactive_analysis_using_llm(df, filename):
    # Prepare the dataset summary
    summary = {
        "filename": filename,
        "columns": list(df.columns),
        "data_types": convert_data_types(df.dtypes.to_dict()),  # Convert pandas types to native types
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "summary_statistics": df.describe().to_dict(),
        "example_values": df.head().to_dict()  # Show first 5 rows as example
    }

    text = f"""
You are an expert data scientist. I have a dataset with the following summary:

Filename: {summary['filename']}
Columns: {summary['columns']}
Data Types: {json.dumps(summary['data_types'], indent=2)}
Number of Rows: {summary['num_rows']}
Number of Columns: {summary['num_columns']}
Summary Statistics: {json.dumps(summary['summary_statistics'], indent=2)}
Example Values: {json.dumps(summary['example_values'], indent=2)}

ONLY Provide Python code.
Based on above summary, separate numerical and categorical columns and suggest the Basic analysis I can perform (For example, summary statistics, counting missing values, correlation matrices, outliers). 
Don't add countplot for categorical columns

if you provide any plots then save them in current directory (use seaborn)
If you suggest a function call, please also explain why it's useful.

read file using:
with open(csv_file, 'rb') as f:
    encoding_result = chardet.detect(f.read())
df = pd.read_csv(csv_file, encoding=encoding_result['encoding'])
"""
    prompt_content = create_prompt_content(text, images_path=[])
    response = call_llm_api(prompt_content)


    code_snippets = re.findall(r'```python(.*?)```', response, re.DOTALL)

    # Execute each code snippet and save its result
    results = {}
    for idx, code in enumerate(code_snippets):
        try:
            # Create a unique key for each snippet
            snippet_name = f"snippet_{idx + 1}"
            
            # Redirect the output of exec to capture the results
            exec_globals = {}
            exec(code, exec_globals)
            
            # If the code generates any output, capture and save it
            # Assuming the code generates variables of interest that you want to store
            results[snippet_name] = exec_globals
            
        except Exception as e:
            print(f"Error executing LLM-suggested code: {e}")
            results[f"snippet_{idx + 1}"] = str(e)

    return {'response': response, 'results':results}


def get_data_summary(df,filename):
    summary = {
        "filename": filename,
        "columns": list(df.columns),
        "data_types": convert_data_types(df.dtypes.to_dict()),  # Convert pandas types to native types
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "summary_statistics": df.describe().to_dict(),
        "example_values": df.head().to_dict()  # Show first 5 rows as example
    }


    text = f"""
    You are an expert data scientist. Give me summary of this data.
    
    Filename: {summary['filename']}
    Columns: {summary['columns']}
    Data Types: {json.dumps(summary['data_types'], indent=2)}
    Number of Rows: {summary['num_rows']}
    Number of Columns: {summary['num_columns']}
    Summary Statistics: {json.dumps(summary['summary_statistics'], indent=2)}
    Example Values: {json.dumps(summary['example_values'], indent=2)}
    
    """
    prompt_content = create_prompt_content(text, images_path=[])
    response = call_llm_api(prompt_content)
    return response


def get_analysis_carried_out(response):
    text = f"""
    You are an expert data scientist. Give me summary of analysis you carried out.

    Given below is the analysys:
    {response}
    
    """
    prompt_content = create_prompt_content(text, images_path=[])
    response = call_llm_api(prompt_content)
    return response


def get_insights_discovered(results):
    images_path = [file for file in os.listdir('.') if file.endswith('.png')]
    text = f"""
    You are an expert data scientist. Give me the insights you discovered from the analysis.

    Given below are the analysys results:
    {results}
    
    """
    prompt_content = create_prompt_content(text, images_path)
    response = call_llm_api(prompt_content)
    return response


def create_story(self_analysis_summary, data_summary, analysis_carried_out, analysis_results):
    images_path = [file for file in os.listdir('.') if file.endswith('.png')]
    text = f"""
You are a data analyst. Narrate a story about the analysis you performed in very Detail. Add these points in the story in detail
    1. The data you received, briefly
    2. The analysis you carried out
    3. The insights you discovered
    4. The implications of your findings (i.e. what to do with the insights)


Data Summary Before applying any change to data: {self_analysis_summary}






Data Summary After applying some changes to data : {data_summary}







Analysis Carried Out : {analysis_carried_out}






Analysis Results : {analysis_results}
"""

    prompt_content = create_prompt_content(text, images_path)
    story = call_llm_api(prompt_content)
    return story

def generate_readme(story, visualizations):
    """ Generate README.md file combining the story and visualizations. """
    with open("README.md", "w") as f:
        f.write("# Automated Analysis Report\n\n")
        f.write(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Analysis Summary\n\n")
        f.write(story + "\n\n")
        f.write("## Visualizations\n\n")
        for image in visualizations:
            f.write(f"![{image}]({image})\n\n")
        print("README.md file has been created.")




def main():
    """ Main function to execute the analysis. """
    if len(sys.argv) != 2:
        print("Usage: uv run autolysis.py <dataset.csv>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    if not os.path.exists(csv_file):
        print(f"Error: File {csv_file} not found.")
        sys.exit(1)

    #Load the dataset
    try:
        with open(csv_file, 'rb') as f:
            encoding_result = chardet.detect(f.read())
            df = pd.read_csv(csv_file, encoding=encoding_result['encoding'])

        print(f"Dataset loaded successfully: {csv_file}")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        sys.exit(1)

    
    # Analyze missing values
    missing_values = analyze_missing_values(df)

    # Detect outliers
    outlier_summary = detect_outliers(df)

    # Perform correlation analysis
    corr_file = correlation_analysis(df)

    # Generate visualizations
    visualizations = []
    if corr_file:
        visualizations.append(corr_file)
        
    images = generate_visualizations(df)
    visualizations.extend(images)

    # Perform Interactive Analysis
    a = interactive_analysis_using_llm(df, csv_file)
    response = a['response']
    results = a['results']
    time.sleep(3)

    # Create Story
    data_summary = get_data_summary(df, csv_file)
    time.sleep(3)

    analysis_carried_out = get_analysis_carried_out(response)
    time.sleep(3)

    analysis_results = get_insights_discovered(results)
    time.sleep(3)

    self_analysis_summary = get_self_analysis_summary(missing_values, outlier_summary)
    time.sleep(3)

    story = create_story(self_analysis_summary, data_summary, analysis_carried_out, analysis_results)

    generate_readme(story, visualizations)


if __name__ == "__main__":
    main()
