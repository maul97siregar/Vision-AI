# How to Run

- Go to `./Backend/Vision`
- Run `python main.py`

# How to Debug in GCP/GKE

- Add credentials to `main.py`
```python
import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your/credential.json"
```
- Add this code in `main.py`
```python
# Imports the Cloud Logging client library
import google.cloud.logging

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
client.setup_logging()
```
- For add logging use standard python logging, example:
```python
# Imports Python standard library logging
import logging

# The data to log
text = "Hello, world!"

# Emits the data using the standard logging module
logging.warning(text)
```
- Go to logging in GKE to see the log

## For More Explanation:
- Go to https://cloud.google.com/logging/docs/setup/python