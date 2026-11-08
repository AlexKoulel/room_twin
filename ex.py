import json 
data = json.loads("{\"Temperature\":15,\"Humidity\":35,\"Pressure\":950}")
data.update({'Prediction': 5,'Residual':5})
print(data)
