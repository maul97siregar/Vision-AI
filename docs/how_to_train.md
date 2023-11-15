# How to Train a New Model

## Before You Train
- Prepare the new data, the text in the image must be clear
- Please [install doccano](https://github.com/doccano/doccano) for annotating the data
- The data must be separated by type, for the example: bbm receipt data can't be mixed with pdam receipt

## Get Text from Image
- Go to /get_text_image
- Upload receipt image to get the text of the image
- Now you have the txt file contains the text of the image

## Annotate The Data
- Run doccano
- Go to 127.0.0.1/8000
- Login with your credential
- **If The Data is New in Doccano/you haven't any project in Doccano**
    - Create New Project
        - Click Create
        - In Create a Project, Select Sequence Labeling, insert Project Name, Description, and Tags.
        - Click Create
- **If You Have Any Project in Doccano**
    - Click The Project
- Add Dataset
    - Go To Dataset
        - Click Action > Import Dataset
        - File Format:
            - Chose TextFile if one txt file is one receipt
            - Chose TextLine if one txt file is many receipt
            - Chose JsonL if you have annotated data from doccano
        - Click Import
- Add Label
    - Go To Labels
        - Click Action > Create Label
        - Add Label name (Field like: bill, merchant, etc)
        - Save and add another
        - Save
- Annotating Data
    - Go To Dataset
        - Click annotate at the first data
        - Block the text contains its label/field, example: bill: block: Total Tagihan: Rp. 1000
        - If done with annotating, click cross icon in top left, to change to check icon for approving document
        - Now you can see in progress, the number of completed sections has increased
        - Now click next icon to go to next data
- Finish Annotating
    - Go to Dataset page
    - Click Actions > Export Dataset
        - Check Export only approved documents
        - File format > Jsonl
        -Export

## Train with Doccano Dataset
- Go To: post /train
- Params:
    - dataset: jsonl file from doccano
    - iteration: 60
    - dropout: 0.5
    - train_split: 0.8
- The result is in zip
- Open the model_info.json
    - make sure that the precission, recall, f value is above 9.0
    ```
    "ents_p": 9.0,
    "ents_r": 9.0,
    "ents_f": 9.0,
    ```

## Add Model
- [Add Model](api_usage.md#add-ai-model)

## Show Model List
- [Show Model](api_usage.md#show-list-ai-model-and-show-model-info)

## Delete Model
- [Delete Model](api_usage.md#delete-ai-model)

## Activate Model
- [Activate Model](api_usage.md#show-active-model-and-select-ai-model)

# Update Model
If there is already a multiple of 100 data, then try to retrain the model with that data so that the model continues to be updated

If there are a small number of new keys, for example only 1-2 keys, then you can use dictionary based to add new keys so that the value can be retrieved quickly without retraining the model

# How to Add Key to Dictionary
- [Add Key to Dictionary](api_usage.md#edit-dictionary-levenshtein)