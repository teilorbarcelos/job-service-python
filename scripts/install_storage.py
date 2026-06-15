import sys
import os
import re

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/install_storage.py <driver-name>")
        print("Supported drivers: s3, gcs, azure, local")
        sys.exit(1)

    driver = sys.argv[1].lower()
    driver_name = driver.capitalize()

    configs = {
        's3': {
            'package': 'boto3',
            'mock_target': 'boto3.client',
            'extra_uses': 'import boto3\nfrom botocore.exceptions import ClientError',
            'setup': """self.s3 = boto3.client(
            's3',
            aws_access_key_id=settings.s3_key,
            aws_secret_access_key=settings.s3_secret,
            region_name=settings.s3_region
        )
        self.bucket = settings.s3_bucket""",
            'env': {
                'S3_KEY': '',
                'S3_SECRET': '',
                'S3_REGION': 'us-east-1',
                'S3_BUCKET': '',
            },
            'test_env': """settings.s3_key = 'test'
    settings.s3_secret = 'test'
    settings.s3_region = 'us-east-1'
    settings.s3_bucket = 'test'"""
        },
        'gcs': {
            'package': 'google-cloud-storage',
            'mock_target': 'google.cloud.storage.Client.from_service_account_json',
            'extra_uses': 'from google.cloud import storage',
            'setup': """self.client = storage.Client.from_service_account_json(settings.gcs_key_file)
        self.bucket = self.client.bucket(settings.gcs_bucket)""",
            'env': {
                'GCS_KEY_FILE': 'credentials.json',
                'GCS_BUCKET': '',
            },
            'test_env': """settings.gcs_key_file = 'test.json'
    settings.gcs_bucket = 'test'"""
        },
        'azure': {
            'package': 'azure-storage-blob',
            'mock_target': 'azure.storage.blob.BlobServiceClient.from_connection_string',
            'extra_uses': 'from azure.storage.blob import BlobServiceClient',
            'setup': """self.service_client = BlobServiceClient.from_connection_string(settings.azure_connection_string)
        self.container_client = self.service_client.get_container_client(settings.azure_container)""",
            'env': {
                'AZURE_CONNECTION_STRING': '',
                'AZURE_CONTAINER': '',
            },
            'test_env': """settings.azure_connection_string = 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net'
    settings.azure_container = 'test'"""
        }
    }

    if driver == 'local':
        print("Local driver is already built-in.")
        return

    if driver not in configs:
        print(f"Error: Driver [{driver}] not supported.")
        sys.exit(1)

    config = configs[driver]

    # 1. Add to requirements.txt (PEP 668 friendly — no direct pip install)
    requirements_path = "requirements.txt"
    if os.path.exists(requirements_path):
        with open(requirements_path, "r") as f:
            reqs = f.read()
        if config['package'] not in reqs:
            with open(requirements_path, "a") as f:
                f.write(f"\n{config['package']}")
            print(f"📋 Added {config['package']} to requirements.txt")
            print(f"   Run 'pip install -r requirements.txt' to install it.")

    # 2. Generate Driver Class
    print(f"📝 Generating {driver_name}Driver.py...")
    template_path = "scripts/templates/storage/Driver.py.tpl"
    with open(template_path, "r") as f:
        content = f.read()
    
    content = content.replace("{DRIVER_NAME}", driver_name)
    content = content.replace("{EXTRA_USES}", config['extra_uses'])
    content = content.replace("{SETUP_LOGIC}", config['setup'])

    driver_path = f"src/infra/storage/drivers/{driver}_driver.py"
    os.makedirs(os.path.dirname(driver_path), exist_ok=True)
    with open(driver_path, "w") as f:
        f.write(content)

    # 3. Generate Test Class
    print(f"🧪 Generating test_{driver}_driver.py...")
    test_template_path = "scripts/templates/storage/Test.py.tpl"
    with open(test_template_path, "r") as f:
        test_content = f.read()

    test_content = test_content.replace("{DRIVER_NAME}", driver_name)
    test_content = test_content.replace("{DRIVER_LOWER}", driver)
    test_content = test_content.replace("{ENV_SETUP}", config['test_env'])
    
    mock_setup = ""
    if 'mock_target' in config:
        mock_setup = f"mocker.patch('{config['mock_target']}')"
    test_content = test_content.replace("{MOCK_SETUP}", mock_setup)

    test_path = f"tests/infra/storage/test_{driver}_driver.py"
    os.makedirs(os.path.dirname(test_path), exist_ok=True)
    with open(test_path, "w") as f:
        f.write(test_content)

    # 4. Update .env and .env.example (simulated)
    print("⚙️ Updating .env and .env.example...")
    for env_file in [".env", ".env.example"]:
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                content = f.read()
            
            for key, value in config['env'].items():
                if f"{key}=" not in content:
                    content += f"\n{key}={value}"
            
            with open(env_file, "w") as f:
                f.write(content)

    print(f"✅ Storage driver [{driver_name}] generated successfully!")
    print(f"💡 To use it, set STORAGE_DISK={driver} in your .env file.")

if __name__ == "__main__":
    main()
