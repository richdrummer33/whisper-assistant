import openai

my_custom_functions = [
    {
        'name': 'move_cursor_to_text_element_ocr',
        'description': 'Move the cursor to the specified text element and perform the click action based on OCR',
        'parameters': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'text': {
                        'type': 'string',
                        'description': 'Text element to move the cursor to'
                    },
                    'click_action': {
                        'type': 'string',
                        'description': 'Click action to perform, either left mouse button (lmb) or right mouse button (rmb)'
                    }
                },
                'required': ['text', 'click_action']
            }
        }
    }
]

##################################################################################################################################################
################################################# SHOULD CALL THE ocr-windows-automation SCRIPT #################################################
##################################################################################################################################################
openai_response = openai.ChatCompletion.create(
    model = 'gpt-3.5-turbo',
    messages = [{'role': 'user', 'content': text_click_tuples}],
    functions = my_custom_functions, 
    function_call = 'auto'
)

print(openai_response)
