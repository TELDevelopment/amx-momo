from crewai import Agent
import requests
import pandas as pd
import json
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
import os
import warnings
from dotenv import load_dotenv
load_dotenv()
warnings.filterwarnings("ignore")

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")
output_file_path = "updated_book.xlsx"


class APIAgent(Agent):
    def execute_api_request(self, method, api_url, data=None, headers=None):
        try:
            if headers is None:
                headers = {'Content-Type': 'application/json'}
            
            if isinstance(headers, str):
                try:
                    headers = json.loads(headers)
                except json.JSONDecodeError:
                    headers = {'Content-Type': 'application/json'}
            
            if data:
                data = json.dumps(data)
            
            response = requests.request(method, api_url, headers=headers, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}

    def fetch_from_excel(self, file_path, output_file_path):
        try:
            # Read the Excel file
            df = pd.read_excel(file_path)

            # Ensure necessary columns exist
            required_columns = {'api_url', 'method'}
            if not required_columns.issubset(df.columns):
                raise ValueError("Excel file must contain 'api_url' and 'method' columns")
            
            if 'body' in df.columns:
                df['body'] = df['body'].fillna('{}')
            
            if 'headers' in df.columns:
                df['headers'] = df['headers'].fillna('{}')
            
            if 'api_response' not in df.columns:
                df['api_response'] = None

            # Iterate through each row, execute API request, and update DataFrame
            results = []
            for index, row in df.iterrows():
                api_url = row['api_url']
                method = row['method'].upper()
                body = json.loads(row['body']) if isinstance(row['body'], str) else None
                headers = json.loads(row['headers']) if 'headers' in row and isinstance(row['headers'], str) else None
                
                result = self.execute_api_request(method, api_url, body, headers)
                formatted_json = json.dumps(result, indent=4)
                df.at[index, 'api_response'] = formatted_json
                print(f"Method: {method} | API: {api_url} => Result: {result}")
                results.append({"api_url": api_url, "method": method, "response": result})
                
            # Save the updated Excel file
            with pd.ExcelWriter(output_file_path, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False)
            
            print("Excel file updated successfully.")
            return results
        except Exception as e:
            print(f"Error processing Excel file: {e}")
            return []
           
class SimilarityAgent(Agent):
    def check_similarity(self, file_path):
        try:
            df = pd.read_excel(file_path)
            
            # Ensure required columns exist
            if 'api_url' not in df.columns or 'api_response' not in df.columns or 'expected_response' not in df.columns:
                raise ValueError("Excel file must contain 'api_url', 'api_response', and 'expected_response' columns.")

            for index, row in df.iterrows():
                api_url = row['api_url']
                api_response = row['api_response']
                expected_response = row['expected_response']
                
                # Construct the prompt for comparison
                prompt = (
                    f"Compare the following API responses for structure only, ignoring values:\n"
                    f"Response 1: {api_response}\n"
                    f"Response 2: {expected_response}\n"
                    f"Are they similar in structure? Return 'True' or 'False'."
                    f"2. If False, provide a brief description of the differences in structure. The difference should be defined for api_response comparing it with expected response"
                )
            # prompt = f"Compare the following API responses for the body, do not consider the values of the fields instead just keys of the response and check if its similar: Consider the following example \nResponse 1: {response1}\nResponse 2: {response2}\nAre they similar? Return 'True' or 'False'."
                response = llm.invoke(prompt)
                
                response_text = response.content.strip().lower()
                
                similarity_result = 'True' if 'true' in response_text else 'False'
                print(similarity_result)
                difference_description = "No difference" if similarity_result == 'True' else response_text.split("false")[-1].strip()
                print("---",difference_description)
                df.at[index, 'similarity_result'] =similarity_result
                df.at[index, 'difference_description'] =difference_description
            # return 'True' if 'true' in similarity_result else 'False'
            with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False)
            print("-----------------------Structure similarity -----------------------")
            print("Excel file updated successfully.")
        except Exception as e:
            return f"Error checking similarity: {e}"
        
class ValueSimilarityAgent(Agent):
    def check_value_similarity(self, file_path):
        try:
            df = pd.read_excel(file_path)
            
            # Ensure required columns exist
            if 'api_url' not in df.columns or 'api_response' not in df.columns or 'expected_response' not in df.columns:
                raise ValueError("Excel file must contain 'api_url', 'api_response', and 'expected_response' columns.")

            for index, row in df.iterrows():
                api_url = row['api_url']
                api_response = row['api_response']
                expected_response = row['expected_response']
                remarks = row['remarks'] 
                
                prompt = (
                    f"Compare the following API responses based on the provided remarks:\n"
                    f"Actual API Response:\n{api_response}\n"
                    f"Expected API Response:\n{expected_response}\n"
                    f"Remarks: {remarks}\n\n"
                    f"Analyze the responses based on the remarks. "
                    f"If the remarks menMtion specific fields, compare the values of those fields only. "
                    f"If there are no specific remarks,do not provide a general comparison.\n"
                    f"Provide your answer as:\n"
                    f"- 'True' if the responses are similar based on the remarks\n"
                    f"- 'False' if there are differences, followed by a short description of the differences."
                )

            # prompt = f"Compare the following API responses for the body, do not consider the values of the fields instead just keys of the response and check if its similar: Consider the following example \nResponse 1: {response1}\nResponse 2: {response2}\nAre they similar? Return 'True' or 'False'."
                response = llm.invoke(prompt)
                # similarity_result = response.content.strip().lower()
                # df.at[index, 'similarity_result'] = 'True' if 'true' in similarity_result else 'False'
                # print(f"API: {api_url} => Similarity: {similarity_result}")
                response_text = response.content.strip().lower()
                # print(response.content)
                # print(response)
                # print(response_text)
                value_similarity_result = 'True' if 'true' in response_text else 'False'
                print(value_similarity_result)
                difference_description = "No difference" if value_similarity_result == 'True' else response_text.split("false")[-1].strip()
                print("---",difference_description)
                df.at[index, 'value_similarity_result'] =value_similarity_result
                df.at[index, 'value_difference_description'] =difference_description
            # return 'True' if 'true' in similarity_result else 'False'
            with pd.ExcelWriter(file_path, engine='openpyxl', mode='w') as writer:
                df.to_excel(writer, index=False)
            print("---------------------Value Similarity Updates-------------------")
            print("Excel file updated successfully.")
        except Exception as e:
            return f"Error checking similarity: {e}"
        
    
if __name__ == "__main__":
    api_agent = APIAgent(name='Test API Agent', role='Tester', goal='Test fetching data', backstory='A simple test agent.')
    similarity_agent = SimilarityAgent(name='Similarity Checker', role='Comparator', goal='Check response similarity for the structure', backstory='An AI designed to verify API data structure consistency.', llm=llm, verbose = True)
    value_similarity_agent = ValueSimilarityAgent(name='Similarity Value Checker', role='Comparator', goal='Check response similarity for the values of each fields', backstory='An AI designed to verify API data structure consistency.', llm=llm)
    file_path = "Book1.xlsx"  # Update with your file path
    
    api_agent.fetch_from_excel(file_path, output_file_path)
    similarity = similarity_agent.check_similarity(output_file_path)
    value_similarity = value_similarity_agent.check_value_similarity(output_file_path)