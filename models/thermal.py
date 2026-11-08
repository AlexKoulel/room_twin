import math

def predict_temperature(temp, t_eq, t, dt):
    return  t_eq + (temp - t_eq) * math.exp(-dt/t)