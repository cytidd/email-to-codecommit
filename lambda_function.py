import boto3
import datetime
import email
import json
import os
import time

s3 = boto3.client('s3')
code_commit = boto3.client('codecommit')
bucket = os.environ['INBOUND_BUCKET']
folder = os.environ['INBOUND_FOLDER']
commit_repo = os.environ['REPO']
commit_branch = os.environ['COMMIT_BRANCH']
approved_from = os.environ['APPROVED_FROM']
NOTE_NAME_KEY = 'note_name'

def lambda_handler(event, context):
    
    # retrieve the message id
    # this will be the key of the object in S3
    messageId = event['Records'][0]['ses']['mail']['messageId']
    
    # fetch and parse the email message from S3
    email_object_body = parse_email(messageId)
    email_body = email.message_from_string(email_object_body)
    
    if approved_from in email_body['From']:
        # parse the note contents
        note_contents = parse_note(email_body)
    
        # parse the note subject
        note_name = parse_note_name(email_body)
    
        # put a file in the CodeCommit repository
        save_to_repo(note_name, note_contents)

        return {
            'statusCode': 200
        }

    else:
        return {
            'statusCode': 401
        }
        


def save_to_repo(note_name, note_contents):
    
    branch_response = code_commit.get_branch(
        repositoryName=commit_repo,
        branchName=commit_branch
    )
    
    commit_id = branch_response['branch']['commitId']
    
    response = code_commit.put_file(
        repositoryName=commit_repo,
        branchName=commit_branch,
        fileContent=note_contents,
        filePath=note_name,
        fileMode='NORMAL',
        parentCommitId=commit_id,
        commitMessage="<NAME HERE> is adding {}".format(note_name),
        name='<NAME HERE>',
        email='<EMAIL_HERE>'
    )
    
    print("save to z response: {}".format(response))
    

def parse_note_name(email_body):
    note_subject = email_body['subject']

    # construct the timestamp
    ts = time.time()
    note_timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d%H%M')
    
    note_name = "{} {}.md".format(note_timestamp, note_subject)
    return note_name


def parse_email(messageId):
    
    # parse the message body from the email
    target_file = "{}/{}".format(folder, messageId)
    
    email_object = s3.get_object(
        Bucket=bucket, 
        Key=target_file)
        
    return email_object['Body'].read().decode('utf-8') 


def parse_note(a):
    
    body = ''
    
    if a.is_multipart():
       for part in a.walk():
           ctype = part.get_content_type()
           cdispo = str(part.get('Content-Disposition'))
    
           # skip any text/plain (txt) attachments
           if ctype == 'text/plain' and 'attachment' not in cdispo:
               body = part.get_payload(decode=True)  # decode
               break
    # not multipart - i.e. plain text, no attachments
    else:
        body = a.get_payload(decode=True)    
    
    return body
    
