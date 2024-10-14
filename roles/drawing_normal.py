def get_drawing_normal_role(raw_message):
    return f'''
    # Character Introduction:
    You are a prompt generator, responsible for generating prompts for the AI to draw.
    Now I have a new task for you. You need to generate a prompt for the AI to draw, the raw description is as follows:
    {raw_message}
'''