from typing import Union
from fastapi import FastAPI, HTTPException, Request 
from pydantic import BaseModel
import pytesseract
import numpy as np
import base64
import cv2
import bcrypt
import mysql.connector #https://www.w3schools.com/python/python_mysql_update.asp 
from googletrans import Translator 
import datetime
from fastapi.middleware.cors import CORSMiddleware #เพื่อจัดการกับ Cross-Origin Resource Sharing (CORS) เป็นเทคโนโลยีที่อนุญาตให้เว็บแอปพลิเคชันทำงานร่วมกับแหล่งที่มาจากโดเมนอื่นๆ

# ถ้าจะทดสอบ ต้องเป็น IP ของ เน็จที่เชื่อมต่อ ณ ขณะนั้น (แนะนำให้ใช้ IP เน็ตมือถือ)
# uvicorn main:app --host 10.160.10.213 --port 8080

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    # allow_origins=["https://receipt-ocr-app-8c0a9.web.app"], #อนุญาต โดเมนให้เข้าถึงข้อมูลจะต้องใช้ *
    allow_origins=["*"],
    allow_credentials=True, #อนุญาตให้ส่ง cookies และ headers ที่เกี่ยวข้องกับ credentials กลับไปยังเซิร์ฟเวอร์
    allow_methods=["*"], #อนุญาตการใช้งานทุก method ใน HTTP request
    allow_headers=["*"], #อนุญาตทุก header ใน HTTP request
)

# Connect Database
# mydb = mysql.connector.connect(
#     host="202.28.34.197",
#     user="web65_64011212185",
#     password="64011212185@csmsu",
#     database="web65_64011212185",
#     connect_timeout=60,  # เพิ่ม timeout
#     read_timeout=60
# )

mydb = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=10,
    pool_reset_session=True,
    host="202.28.34.197",
    user="web65_64011212185",
    password="64011212185@csmsu",
    database="web65_64011212185",
)


mycursor = mydb.cursor()

class Item(BaseModel):
    image_base64 : str

class User(BaseModel):
    name : str
    email : str
    password : str
    photo : str

class LogIn(BaseModel):
    name_or_email : str
    password : str

class User_Image(BaseModel):
    name : str
    base64 : str
    UID : int

def readb64(uri):
   nparr = np.fromstring(base64.b64decode(uri), np.uint8)  
   img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
   return img

@app.get("/")
async def read_root():
    return {"Hello": "Hello World !!!"}

# API ในการทำ ocr โดยการรับพารามิเตอร์ข้อมูลรูปภาพที่เป็น base64
@app.post("/ocr")
async def image_Processing(data : Item):
    img = readb64(data.image_base64)
    text = pytesseract.image_to_string(img, lang='tha+eng')  
    ocr_text_delete_spaces = text.replace(' ', '') 

    #df = pytesseract.image_to_data(img, lang='tha+eng', pandas_config=1) 
    #print(df)

    return {"ocr_text_delete_spaces": ocr_text_delete_spaces} 

# API ในการทำ translate โดยรับพารามิเตอร์ 2 ตัวก็คือ ข้อความที่ต้องการเเปลภาษา เเละ ภาษาเป้าหมาย
@app.post("/translate")
async def translate_text(translate_model : Request):
    translate_model_json = await translate_model.json()
    translator = Translator()
    translated_text = translator.translate(translate_model_json['text_to_translate'], dest=translate_model_json['target_language'])
    return {"translated_text": translated_text.text}

# API ในการสมัครสมาชิก โดยรับพารามิเตอร์ name, email, password, photo
@app.post("/user")
async def insert_user(user : User):
    sql = "SELECT * FROM User WHERE email = %s"
    mycursor.execute(sql, (user.email,))
    myresult = mycursor.fetchall()
    if myresult:
        raise HTTPException(status_code=401, detail="Email already exists")
    else:
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user.password.encode(), salt) 
        user.password = hashed_password

        sql = "INSERT INTO User (name, email, password, photo) VALUES (%s, %s, %s, %s)"
        val = (user.name, user.email, user.password, user.photo)
        mycursor.execute(sql, val)
        mydb.commit()
        return {"1 record inserted, ID:": mycursor.lastrowid}

# API ในการ Login โดยรับพารามิเตอร์ ชื่อผู้ใช้ หรือ อีเมลผู้ใช้ เเละ password
@app.post("/user/LogIn")
async def user_LogIn(logIn : LogIn):
    sql = "SELECT * FROM User WHERE name = %s OR email = %s"
    val = (logIn.name_or_email, logIn.name_or_email)
    mycursor.execute(sql, val)
    myresult = mycursor.fetchall()
    if myresult:
        UID = myresult[0][0]
        if bcrypt.checkpw(logIn.password.encode(), myresult[0][3].encode()):
            sql = "SELECT User.UID, User.name, User.email, User.password, User.photo, COUNT(Friend.UID) AS friend_count FROM User LEFT JOIN Friend ON User.UID = Friend.UID WHERE User.UID = %s GROUP BY User.UID, User.name, User.email, User.password, User.photo"
            val = (UID, )
            mycursor.execute(sql, val)
            myresult = mycursor.fetchall()
            return {"UID": myresult[0][0], "name": myresult[0][1], "email": myresult[0][2], "password": myresult[0][3], "photo": myresult[0][4], "friend_count": myresult[0][5]}
        else:

            print(myresult[0][3].encode())##############################

            raise HTTPException(status_code=401, detail="The password is incorrect.")
    else:
        raise HTTPException(status_code=404, detail="This name or email was not found.")

# API ในการเเสดงผู้ใช้ทั้งหมดที่ไม่ใช่เพื่อน รับพารามิเตอร์ UID ของเราเอง
@app.get("/user/{UID}")
async def getUser(UID: int):
    sql = "SELECT User.* FROM User LEFT JOIN Friend ON User.UID = Friend.friendID AND Friend.UID = %s WHERE Friend.FID IS NULL AND User.UID <> %s"
    val = (UID, UID)
    mycursor.execute(sql, val)
    myresult = mycursor.fetchall()
    user_list = []
    for user_data in myresult:
        user_dict = {"UID": user_data[0], "name": user_data[1], "email": user_data[2], "password": user_data[3], "photo": user_data[4]}
        user_list.append(user_dict)
    return user_list

# API ในการค้นหาผู้ใช้ที่ไม่ใช่เพื่อน โดยค้นหาจากชื่อ รับพารามิเตอร์ 2 ตัวคือ ชื่อเพื่อนที่ต้องการค้นหา เเละ UID ของเราเอง
@app.get("/user/name/{name}/UID/{UID}")
async def getUsers(name: str, UID: int):
    sql = "SELECT User.* FROM User LEFT JOIN Friend ON User.UID = Friend.friendID AND Friend.UID = %s WHERE Friend.FID IS NULL AND User.UID <> %s AND User.name LIKE %s"
    NameData = '%' + name + '%'
    val = (UID, UID, NameData)
    mycursor.execute(sql, val)
    myresult = mycursor.fetchall() 
    user_list = []
    for user_data in myresult:
        user_dict = {"UID": user_data[0], "name": user_data[1], "email": user_data[2], "password": user_data[3], "photo": user_data[4]}
        user_list.append(user_dict)
    return user_list

# API ในการ update ข้อมูลผู้ใช้ โดยรับพารามิเตอร์คือ UID ที่ต้องการ update , name, password, photo
@app.put("/update/user/{UID}")
async def update_User(UID : int, user_data : Request):
    user_data_json = await user_data.json()
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user_data_json['password'].encode(), salt) 

    sql = "UPDATE User SET name = %s, password = %s, photo = %s WHERE UID = %s"
    val = (user_data_json['name'], hashed_password, user_data_json['photo'], UID)
    mycursor.execute(sql, val)
    mydb.commit()
    if mycursor.rowcount == 1:
        return {"record(s) affected" : mycursor.rowcount}
    else:
        raise HTTPException(status_code=500, detail="update failed")

# API ในการเเสดงรูปภาพของผู้ใช้นั้นๆ รับพารามิเตอร์ UID
@app.get("/user/image/{UID}")
async def getImages(UID: int):
    sql = "SELECT Image.MID, Image.name, Image.base64, Image.UID FROM User INNER JOIN Image ON User.UID = Image.UID WHERE User.UID = %s"
    val = UID
    mycursor.execute(sql, (val, ))
    myresult = mycursor.fetchall()
    image_list = []
    for image_data in myresult:
        image_dict = {"MID": image_data[0], "name": image_data[1], "base64": image_data[2] , "UID": image_data[3]}
        image_list.append(image_dict)
    return image_list

# API ในการเพิ่มรูปภาพของผู้ใช้นั้นๆ รับพารามิเตอร์ name = ชื่อของรูปภาพ, base64 = ข้อมูลรูปภาพ, UID = ของผู้ใช้
@app.post("/user/image")
async def insert_image(user_image : User_Image):
    sql = "INSERT INTO Image (name, base64, UID) VALUES (%s, %s, %s)"
    val = (user_image.name, user_image.base64, user_image.UID)
    mycursor.execute(sql, val)
    mydb.commit()
    return {"1 record inserted, ID:": mycursor.lastrowid}

# API ในการลบรูปภาพของผู้ใช้นั้นๆ รับพารามิเตอร์ UID = ไอดีของรูปภาพ
@app.delete("/user/image/{MID}")
async def delete_image(MID: int):
    sql = "DELETE FROM Image WHERE MID = %s"
    val = (MID, )
    mycursor.execute(sql, val)
    mydb.commit()
    return {"record(s) deleted": mycursor.rowcount}

# API ในการเพิ่มเพื่อนของผู้ใช้คนนั้นๆ รับพารามิเตอร์ friendID = ไอดีของผู้ใช้ที่ต้องการเพิ่มเป็นเพื่อน, UID ของผู้ใช้
@app.post("/friend")
async def insert_friend(friend_model : Request):
    friend_model_json = await friend_model.json()
    sql = "SELECT * FROM Friend WHERE friendID = %s and UID = %s"
    val = (friend_model_json['friendID'], friend_model_json['UID'])
    mycursor.execute(sql, val)
    myresult = mycursor.fetchall()
    if myresult:
        raise HTTPException(status_code=401, detail="Be Friend")
    else:
        sql = "INSERT INTO Friend (friendID, UID) VALUES (%s, %s)"
        val = (friend_model_json['friendID'], friend_model_json['UID'])
        mycursor.execute(sql, val)
        mydb.commit()

        sql = "INSERT INTO Friend (friendID, UID) VALUES (%s, %s)"
        val = (friend_model_json['UID'], friend_model_json['friendID'])
        mycursor.execute(sql, val)
        mydb.commit()
        return {"1 record inserted, ID:": mycursor.lastrowid}

# API ในการเเสดงเพื่อนของ user คนนั้นๆ รับพารามิเตอร์คือ UID ของผู้ใช้
@app.get("/friend/{UID}")
async def get_friend(UID: int):
    sql = "SELECT Friend.FID, Friend.friendID, User.name, User.photo FROM Friend INNER JOIN User ON Friend.friendID = User.UID WHERE Friend.UID = %s"
    val = UID
    mycursor.execute(sql, (val, ))
    myresult = mycursor.fetchall()
    friend_list = []
    for friend_data in myresult:
        friend_dict = {"FID": friend_data[0], "friendID": friend_data[1], "name": friend_data[2], "photo": friend_data[3]}
        friend_list.append(friend_dict)
    return friend_list

# API ในการลบเพื่อนของผู้ใช้คนนั้นๆ รับพารามิเตอร์คือ friendID = ไอดีของเพื่อน, UID = ไอดีของตัวเอง
@app.delete("/friend")
async def delete_friend(friend_model : Request):
    friend_model_json = await friend_model.json()
    sql = "DELETE FROM Friend WHERE friendID = %s and UID = %s"
    val = (friend_model_json['friendID'], friend_model_json['UID'])
    mycursor.execute(sql, val)
    mydb.commit()

    sql = "DELETE FROM Friend WHERE friendID = %s and UID = %s"
    val = (friend_model_json['UID'], friend_model_json['friendID'])
    mycursor.execute(sql, val)
    mydb.commit()
    return {"record(s) deleted": mycursor.rowcount} 

# API ในการส่งข้อความของผู้ใช้คนนั้นๆ ไปหาเพื่อน รับพารามิเตอร์คือ FID = ไอดีของการเป็นเพื่อน, friendID = ไอดีของเพื่อน,
# UID = ไอดีของตัวเอง, name = ชื่อของตัวเอง, massage = ข้อความที่ต้องการส่งไป
@app.post("/massage/sent")
async def insert_massage(massage_model : Request):
    massage_model_json = await massage_model.json()
    sql = "INSERT INTO Massage (name, massage) VALUES (%s, %s)"
    val = (massage_model_json['name'], massage_model_json['massage'], )
    mycursor.execute(sql, val)
    mydb.commit()
    if mycursor.rowcount == 1:
        MID = mycursor.lastrowid
        sql = "SELECT FID FROM Friend WHERE friendID = %s AND UID = %s"
        val = (massage_model_json['UID'], massage_model_json['friendID'], ) 
        mycursor.execute(sql, val)
        myresult = mycursor.fetchall()
        if myresult:
            FID = myresult[0][0]
            current_datetime = datetime.datetime.now()
            formatted_datetime = current_datetime.strftime('%Y-%m-%d %H:%M:%S') 
            sql = "INSERT INTO Sent (FID, MID, time) VALUES (%s, %s, %s)"
            val = (massage_model_json['FID'], MID, formatted_datetime, )
            mycursor.execute(sql, val)
            mydb.commit()
 
            sql = "INSERT INTO Sent (FID, MID, time) VALUES (%s, %s, %s)"
            val = (FID, MID, formatted_datetime, )
            mycursor.execute(sql, val)
            mydb.commit()
            return {"record inserted.": mycursor.rowcount} 
    else:
        raise HTTPException(status_code=500, detail="insert failed")

# API ในการเเสดงช่องแชทของผู้ใช้ที่ Login กับเพื่อนของเขา รับพารามิเตอร์คือ FID = ไอดีของการเป็นเพื่อน
@app.get("/friend/massage/{FID}")
async def get_massage(FID : int):
    sql = "SELECT Massage.MID, Massage.name, Massage.massage, Sent.time FROM Friend INNER JOIN Sent ON Friend.FID = Sent.FID INNER JOIN Massage ON Sent.MID = Massage.MID WHERE Friend.FID = %s ORDER BY Sent.time"
    val = FID
    mycursor.execute(sql, (val, ))
    myresult = mycursor.fetchall() 
    massage_list = []
    for massage_data in myresult:
        massage_dict = {"MID" : massage_data[0], "name" : massage_data[1], "massage" : massage_data[2], "time" : massage_data[3]}
        massage_list.append(massage_dict)
    return massage_list

# API ในการลบข้อความบางประโยค ใน ช่องแชทของผู้ใช้ที่ Login กับเพื่อนของเขา รับพารามิเตอร์คือ MID = ไอดีของข้อความนั้นๆ
@app.delete("/friend/massage/{MID}")
async def delete_OneMassage(MID : int):
    sql = "DELETE FROM Sent WHERE MID = %s"
    val = (MID, )
    mycursor.execute(sql, val)
    mydb.commit()
    if mycursor.rowcount:
        sql = "DELETE FROM Massage WHERE MID = %s"
        val = (MID, )
        mycursor.execute(sql, val)
        mydb.commit()
        return {"record(s) deleted": mycursor.rowcount}
    else:
        raise HTTPException(status_code=500, detail="delete failed") 
    

# API select ผู้ใช้ด้วย ID
@app.get('/select/user/{UID}')
async def getUserById(UID : int):
    sql = "SELECT User.UID, User.name, User.email, User.password, User.photo, COUNT(Friend.UID) AS friend_count FROM User LEFT JOIN Friend ON User.UID = Friend.UID WHERE User.UID = %s GROUP BY User.UID, User.name, User.email, User.password, User.photo"
    val = (UID, )
    mycursor.execute(sql, val)
    myresult = mycursor.fetchall()
    return {"UID": myresult[0][0], "name": myresult[0][1], "email": myresult[0][2], "password": myresult[0][3], "photo": myresult[0][4], "friend_count": myresult[0][5]}
    