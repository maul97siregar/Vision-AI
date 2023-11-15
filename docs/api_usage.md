# Predict BBM
![Predict BBM](images/predict_bbm.png)

To get key and values in bbm receipt 
- link: post /predict_bbm
- supported format: jpg, jpeg, png
- supported merchant: pertamina, shell, vivo
- params:
    - image: bbm receipt image
- result example:
    - json

![Predict BBM](images/result_bbm.png)
---
# Predict PDAM
![Predict PDAM](images/predict_pdam.png)
To get key and values in pdam receipt
- link: post /predict_pdam
- supported format: jpg, jpeg, png
- supported merchant: pos, indomaret, alfamart, palyja, tokopedia, go mobile
- params:
    - image: pdam receipt image
- result example:
    - json

![Predict PDAM](images/result_pdam.png)
---
# Get Text From Image
![Get Text From Image](images/get_text_image.png)
To get text in document/photo
- link: post /get_text_image
- supported format: jpg, jpeg, png
- params:
    - document/photo with supported format
- result example:
    - txt file
    
![Get Text From Image](images/result_get_text.png)
---
# Train Model
![Train Model](images/train.png)
To train ner model 
- link: post /train
- params:
    - iteration: train iteration/epoch, positive int > 0
    - dropout: dropout value, float 0.0 - 1.0
    - train_split: train split value, float 0.1 - 0.9
    - dataset: jsonl dataset from doccano
- result example:
    - model in zip

![Train Model](images/result_train.png)
---
# Edit Dictionary (Levenshtein)
![Levenshtein Utils](images\levenshtein_utils.png)
Utilization dictionary based ner, add or remove key/label in dictionary
- to show dictionary list:
    - link: get /levenshtein_utils
- to add or delete key/label in dictionary:
    - link: post /levenshtein_utils
    - params:
        - receipt_type: bbm or pdam
        - field: field value
        - key: key to be added or removed
        - method: add or delete
- result example: show dictionary:

![Levenshtein Utils](images\levenshtein_utils_get.png)
---
# Add AI Model
For adding a new model to server
- link: post /add_model
- params:
    - model_name: model name
    - file: model zip from training
---
# Show list AI model and show model info
- To show list of AI models in server
    - link: get /show_model
- To show model info, click a model in list
    - link: get /data/<path:model_name>
---
# Delete AI Model
For deleting a model in server
- link: delete /delete_model/<string: model_name>
---
# Show active model and select AI Model
- To show current active model
    - link: get /select_model
- For selecting/replace active model
    - link: post /select_model
    - params:
        - receipt_type: bbm, pdam
        - model_name: model name to be activated
