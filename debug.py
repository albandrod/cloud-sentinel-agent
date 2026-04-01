import os
from dotenv import load_dotenv

load_dotenv(override=True)

print("--- DEBUG DE VARIABLES ---")
print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
print(f"Deployment: {os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT_NAME')}")
print(f"API Key: {os.getenv('AZURE_OPENAI_API_KEY')[:5]}*****") # Solo los primeros 5 caracteres por seguridad