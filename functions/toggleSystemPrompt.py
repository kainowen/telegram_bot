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
        self.PERSONALITY = ""
        self.SYSTEM_PROMPT = ""

    def __call__(self,PERSONALITIES,override: str):
        print("Starting: ToggleSystemPropmt")
        
        lowercased_list = [item.lower().replace(".txt", "") for item in self.personalities] # Converts personality list to lower case for matching when toggling specific profiles

        if override != "":
            if override.lower() in lowercased_list:
                self.index = lowercased_list.index(override.lower())
            else:
                print("Personality name not recognised")
            
        else:
            personalityCount = len(self.personalities)
            if int(self.index) >= int(personalityCount) - 1:
                self.index = 0
            else: 
                self.index += 1
            
        self.PERSONALITY = str(Path(__file__).resolve().parent.parent) + PERSONALITIES +  self.personalities[self.index]

        if not os.path.exists(self.PERSONALITY):
            self.SYSTEM_PROMPT =  """You are MARX, a helpful, friendly, and casual AI assistant. 
                        Keep answers brief and easy to understand. Avoid unnecessary fluff. 
                        Let me know if you don't know the answer to something. Don't make things up."""
        else:
            with open(self.PERSONALITY, 'r') as f:
                self.SYSTEM_PROMPT=  f.read()
        return(self.SYSTEM_PROMPT)        
    
    def getName(self):
        print("Starting: ToggleSystemPropmt.getName")
        return self.personalities[self.index].replace(".txt","")