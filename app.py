import time
from pathlib import Path
from detect import run
import yaml
from loguru import logger
import os
import boto3
import requests
import json
from decimal import Decimal

images_bucket = os.environ['BUCKET_NAME']
queue_url = os.environ['SQS_QUEUE_URL']
alb_url = os.environ['ALB_URL']

sqs_client = boto3.client('sqs', region_name='eu-east-1')
s3_client = boto3.client('s3')

with open("data/coco128.yaml", "r") as stream:
    names = yaml.safe_load(stream)['names']

def consume():
    
    logger.info('\nWaiting for love..\n')

    while True:
        response = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=5)

        if 'Messages' in response:
            message = json.loads(response['Messages'][0]['Body'])
            receipt_handle = response['Messages'][0]['ReceiptHandle']

            # Use the ReceiptHandle as a prediction UUID
            prediction_id = response['Messages'][0]['MessageId']

            logger.info(f'prediction: {prediction_id}. start processing')

            # Receives a URL parameter representing the image to download from S3
            # TODO extract from `message`
            img_name = message.get('photo_path', '')
            chat_id = message.get('chat_id', '')

            logger.info(f'\nimg_name = {img_name}\nchat_id = {chat_id}\n')

            # TODO download img_name from S3, store the local image path in original_img_path
            original_img_path = img_name
            if "photos" in img_name:
                os.makedirs("photos", exist_ok=True)
                img_name = img_name.split('/')[-1]

            s3_client.download_file(images_bucket, original_img_path, original_img_path)
            logger.info(f'prediction: {prediction_id}/{original_img_path}. Download img completed')

            # Predicts the objects in the image
            run(
                weights='yolov5s.pt',
                data='data/coco128.yaml',
                source=original_img_path,
                project='static/data',
                name=prediction_id,
                save_txt=True
            )

            logger.info(f'prediction: {prediction_id}/{original_img_path}. done')

            # This is the path for the predicted image with labels
            # The predicted image typically includes bounding boxes drawn around the detected objects, along with class labels and possibly confidence scores.
            predicted_img_path = Path(f'static/data/{prediction_id}/{img_name}')

            # TODO Uploads the predicted image (predicted_img_path) to S3 (be careful not to override the original image).
            s3_predicted_path = f'predictions/{img_name}'
            s3_client.upload_file(str(predicted_img_path), images_bucket, s3_predicted_path)

            # Parse prediction labels and create a summary
            pred_summary_path = Path(f'static/data/{prediction_id}/labels/{img_name.split(".")[0]}.txt')
            if pred_summary_path.exists():
                with open(pred_summary_path) as f:
                    labels = f.read().splitlines()
                    labels = [line.split(' ') for line in labels]
                    labels = [{
                        'class': names[int(l[0])],
                        'cx': Decimal(l[1]),
                        'cy': Decimal(l[2]),
                        'width': Decimal(l[3]),
                        'height': Decimal(l[4]),
                    } for l in labels]

                logger.info(f'prediction: {prediction_id}/{original_img_path}. prediction summary:\n\n{labels}')

                prediction_summary = {
                    'prediction_id': prediction_id,
                    'original_img_path': str(original_img_path),
                    'predicted_img_path': str(predicted_img_path),
                    'chat_id': chat_id,
                    'labels': labels,
                    'time': Decimal(time.time())
                }

                # TODO store the prediction_summary in a DynamoDB table
                store_in_dynamodb(prediction_summary)

                # TODO perform a GET request to Polybot to `/results` endpoint
                logger.info(f'\nSending GET request pred_ID: {prediction_id}\n')
                send_request_to_polybot(prediction_id)
                logger.info(f'\nGET request sent.\n')

            # Delete the message from the queue as the job is considered as DONE
            sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

def store_in_dynamodb(summary_dic):
    dynamodb_resource = boto3.resource('dynamodb', region_name='eu-east-1')
    table = dynamodb_resource.Table('ibraheemg-dynamodb-table')
    try:
        res = table.put_item(Item=summary_dic)
        logger.info(f'Saved successfully to DynamoDB')
        return res
    except Exception as e:
        logger.error(f"Error adding item to DynamoDB: {e}")
        return None

def send_request_to_polybot(prediction_id):
    try:
        #polybot_results_url = f'https://{alb_url}/results?predictionId={prediction_id}'
        polybot_results_response = requests.get(f'http://{alb_url}/results?predictionId={prediction_id}', verify=False)
        logger.info(f'Status Code: {polybot_results_response.status_code}')
        polybot_results_response.raise_for_status()
        return 'OK'
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error occurred: {http_err}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    consume()
