import pandas as pd
import random
import csv

if __name__ == '__main__':
    inx_path = '/home/sergo/Work/Intel_Competition/data-original/idx.txt'
    df = pd.read_csv(inx_path)
    records_num = len(df)
    delete_inx = random.sample(range(0, records_num), int(records_num * 0.97))
    df.drop(df.index[delete_inx], inplace=True)
    df.to_csv("/home/sergo/Work/Intel_Competition/data-original/idx-reduced.txt", index=False)