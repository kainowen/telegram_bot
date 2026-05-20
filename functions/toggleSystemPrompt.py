import os
from pathlib import Path


class ToggleSystemPropmt:
    '''Allows for toggling between different system prompts'''
  
    PERSONALITY = ""

    def __init__(self,PERSONALITIES):
        print("Initialising: ToggleSystemPropmt")
        folder_path = str(Path(__file__).resolve().parent.parent) + str(PERSONALITIES)
        personalityList = []
        for entry in os.scandir(folder_path):
            if entry.is_file():
               personalityList.append(entry.name)
        self.personalities = personalityList
        self.index = len(self.personalities)
  
    SYSTEM_PROMPT = ""

    def __call__(self,PERSONALITIES):
        print("Starting: ToggleSystemPropmt")
        personalityCount = len(self.personalities)
        if int(self.index) >= int(personalityCount) - 1:
            self.index = 0
        else: 
            self.index += 1
        
        PERSONALITY = str(Path(__file__).resolve().parent.parent) + PERSONALITIES +  self.personalities[self.index]

        if not os.path.exists(PERSONALITY):
            SYSTEM_PROMPT =  """You are MARX, a helpful, friendly, and casual AI assistant. 
                        Keep answers brief and easy to understand. Avoid unnecessary fluff. 
                        Let me know if you don't know the answer to something. Don't make things up."""
        else:
            with open(PERSONALITY, 'r') as f:
                SYSTEM_PROMPT=  f.read()
        return(SYSTEM_PROMPT)        
    
    def getName(self):
        print("Starting: ToggleSystemPropmt.getName")
        return self.personalities[self.index].replace(".txt","")