# Use the official AWS Lambda Python 3.12 base image
FROM public.ecr.aws/lambda/python:3.12

# Set the working directory in the container
WORKDIR /var/task

# --- Layer Caching Optimization ---
# Copy only the requirements file first.
# This step only re-runs if requirements.txt changes.
COPY src/requirements.txt .

# Install Python dependencies.
# The dependencies (awswrangler, pandas, requests) are large, so we want this layer to cache.
RUN pip install -r requirements.txt --target .

# Copy the Lambda function code.
# This step re-runs only if lambda_etl.py changes (which is fast).
COPY src/lambda_etl.py .

# Set the CMD to your handler (the default entry point for the Lambda function)
# The format is "module_name.function_name"
CMD [ "lambda_etl.lambda_handler" ]