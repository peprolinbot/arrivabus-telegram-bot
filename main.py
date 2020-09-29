import threading 
import os
from datetime import datetime
from datetime import timedelta
import telegram
from telegram.ext import Updater  
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import CallbackQueryHandler
from telegram.ext import Filters
from telegram import KeyboardButton
from telegram import ReplyKeyboardMarkup
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from config.telegram import *
from time import sleep
import sqlite3
import api as arrivapi

#Sets up the telegram bot
bot = telegram.Bot(token=token)  
updater = Updater(bot.token, use_context=True)

#Creates a class for database
class db:
    def __init__(self, dbFile):
        self.dbFile = dbFile

    def getFavoriteStops(self, userId):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId,)
        dbCursor.execute("SELECT stopId FROM favoriteStops WHERE telegramUserId=?", s)
        returnStops=[]
        for row in dbCursor.fetchall():
            returnStops.append(row[0])
        return returnStops

    def getFavoritesStopsNames(self, userId):
        stops = self.getFavoriteStops(userId)
        returnStops = []
        for stop in stops:
            returnStops.append(arrivapi.stopIdToName(stop, "nom_web"))
        return returnStops

    def insertNewfavoriteStop(self, userId, stopId):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId, stopId,)
        dbCursor.execute("INSERT INTO favoriteStops VALUES(?,?)", s)
        db.commit()
    
    def deleteFavoriteStop(self, userId, stopId):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId, stopId,)
        dbCursor.execute("DELETE FROM favoriteStops WHERE telegramuserId = ? AND stopId = ?", s)
        db.commit()


    def autoInsertToExpedition(self, userId, arg):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId,)       
        dbCursor.execute("SELECT * FROM activeExpeditions WHERE telegramUserId=?", s)
        out=dbCursor.fetchall()
        if out == [] :
            arg = arrivapi.nameToStopId(arg)
            s = (userId, arg,)
            dbCursor.execute("INSERT INTO activeExpeditions VALUES(?, ?, NULL, NULL)", s)
            columnName="originStopId"
        else:
            i=0    
            for column in out[0]:
                if column == None:
                    dbCursor.execute("PRAGMA table_info(activeExpeditions)")
                    columnName=dbCursor.fetchall()[i][1]
                    if columnName == "date":
                        spacerChar = ''.join([i for i in arg if not i.isdigit()])[0]
                        arg = arg.replace(spacerChar, "-")
                    else:
                        arg = arrivapi.nameToStopId(arg)
                    s = (arg, userId,)
                    dbCursor.execute("UPDATE activeExpeditions SET " + columnName + " = ? WHERE telegramUserId = ?", s)
                    break
                i += 1
        
        db.commit()
        return columnName


    def removeExpedition(self, userId):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId,)       
        dbCursor.execute("DELETE FROM activeExpeditions WHERE telegramUserId=?", s)
        db.commit()

    def getExpeditionValues(self, userId):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId,)       
        dbCursor.execute("SELECT * FROM activeExpeditions WHERE telegramUserId=?", s)
        out=dbCursor.fetchall()
        if out == []:
            return None
        returnValues = []
        for column in out[0]:
            if column != None:
                returnValues.append(column)
        returnValues.pop(0)
        return returnValues
    
    def deleteEverythingFromUser(self, userid):
        db = sqlite3.connect(self.dbFile)
        dbCursor = db.cursor()
        s = (userId,)       
        dbCursor.execute("DELETE FROM activeExpeditions WHERE telegramUserId=?", s)
        dbCursor.execute("DELETE FROM favoriteStops WHERE telegramUserId=?", s)
        db.commit()



mainDb = db("database.db")

#Sets up menus
class simpleMenu:
    def __init__(self, keyboard, presentationText):
        self.keyboard = keyboard
        self.keyboardObj = ReplyKeyboardMarkup(keyboard)
        self.presentationText = presentationText
    
    def send(self, update, context, presentationText=None):
        if presentationText == None:
            presentationText = self.presentationText
        bot.sendMessage(chat_id=update.effective_chat.id, text=presentationText, reply_markup=self.keyboardObj)

class userSpecificMenu:
    def __init__(self, buttonTextListFunction, presentationText, extraKeyboardAtStart=[]):
        self.buttonTextListFunction = buttonTextListFunction
        self.extraKeyboardAtStart = extraKeyboardAtStart
        self.presentationText = presentationText
    
    def getKeyboardObj(self, userId):
        keyboard = [self.extraKeyboardAtStart]
        for buttonText in self.buttonTextListFunction(userId):
            keyboard += [[KeyboardButton(buttonText)]]
        keyboardObj = ReplyKeyboardMarkup(keyboard)
        return keyboardObj
    
    def send(self, update, context, presentationText=None):
        if presentationText == None:
            presentationText = self.presentationText
        KeyboardObj = self.getKeyboardObj(update.effective_chat.id)
        bot.sendMessage(chat_id=update.effective_chat.id, text=presentationText, reply_markup=KeyboardObj)


mainMenu = simpleMenu([[KeyboardButton("♥️Paradas favoritas")],
                        [KeyboardButton("🔍Resultados")]], "Elige que quieres hacer:")

allFavoriteStopsMenu = userSpecificMenu(mainDb.getFavoritesStopsNames, "Elige una parada:", [KeyboardButton("⬅️Atrás")])


def generateExpeditionsText(expeditionsJson, idaOrOrigen):

    longestExpeditionName = 0
    for expedition in expeditionsJson[idaOrOrigen]:
        for expeditionStop in expedition["parada_expediciones"]:
            expeditionName = expedition["parada_origen"]["nom_parada"]+"\U000027A1"+expedition["parada_destino"]["nom_parada"]
            if len(expeditionName) > longestExpeditionName:
                longestExpeditionName = len(expeditionName)

    result = [""]
    resultCount=0
    for expedition in expeditionsJson[idaOrOrigen]:
        expeditionStart = datetime.strptime(expedition["hora_salida"], "%Y-%m-%dT%H:%M:%S+02:00")
        expeditionEnd = datetime.strptime(expedition["hora_llegada"], "%Y-%m-%dT%H:%M:%S+02:00")
        expeditionDuration = timedelta(hours=expeditionStart.hour, minutes=expeditionStart.minute) - timedelta(hours=expeditionEnd.hour, minutes=expeditionEnd.minute)
        for expeditionStop in expedition["parada_expediciones"]:
            arriveTime = timedelta(hours=int(expeditionStop["horaSalida"].split(":")[0]), minutes=int(expeditionStop["horaSalida"].split(":")[1])) + expeditionDuration
            arriveTime = str(arriveTime)[:-3]
            if len(arriveTime) < 5:
                arriveTime = "0" + arriveTime
            expeditionName = expedition["parada_origen"]["nom_parada"]+"\U000027A1"+expedition["parada_destino"]["nom_parada"]
            if len(expeditionName) < longestExpeditionName:
                for i in range((longestExpeditionName - len(expeditionName)) * 3):
                    expeditionName += " "
            if len(result[resultCount].encode("utf8")) > 4096:
                result.append("")
                resultCount += 1
            result[resultCount] += expeditionName+"    "+expeditionStop["horaSalida"]+"    "+arriveTime+"    "+str(expedition["tarifa_basica"]/100)+"€\n" 
    spacing=""
    for i in range(longestExpeditionName):
        spacing+=" "
    spacing += "          "
    result.insert(0, "==========*"+idaOrOrigen.upper()+"*==========\n\n*Nombre"+spacing+"Salida"+"    "+"Llegada"+"  "+"Precio*\n")
    return result

def start(update, context): #Start command. Presents itself and sends an in-keyboard menu
    msg = "¡Hola!👋 soy " + botName + ", y puedo ayudarte a buscar los horarios para los buses de la compañía Arriva Gaalicia. Usa el menu de tú teclado o escribe /help para ver los comandos disponibles."
    mainMenu.send(update, context, msg)

def help(update, context): #Help command. Tells what does each command
    context.bot.sendMessage(chat_id=update.effective_chat.id, text='''❓ Ayuda e información ❓

👉Uso básico
Manda el nombre de una parada o escoge una de tu lsita de favoritas para eligirla como origen y repite para poner otra como destino. En caso de que desees una fecha diferente al día de hoy usa /setDate Día-mes-año, ej. /setDate 27-2-2020. Y recibe los resultados con /result.

👉Guardar paradas
Puedes guardar tus paradas favoritas o más usadas en una lista que podrás consultar posteriormente. Para guardar una parada, búscala primero, y a continuación, pulsa sobre el botón Añadir a favoritos, justo debajo del mensaje recibido.
Para ver tus paradas guardadas, pulsa en paradas favoritas en el menú de tu teclado. Todas tus paradas guardadas aparecerán en forma de botones, y pulsando sobre ellas,podrás eligirlas como origen o destino.
Cuando hagas click sobre una parada, puedes eliminarla haciendo click en el botón "Eliminar de favoritos".

ℹ️Lista completa de comandos disponibles
🔸Búsqueda de paradas: envía el nombre de una parada directamente, o precedido por /search
🔸/result: muestra las rutas disponibles con lso parámetros especificados
🔸/setDate: Fija la el día del que quieres obtener los buses
🔸/borrar_todo: borra todos tus datos (paradas guardadas) del bot
🔸/help: este comando
🔸/about: información sobre el bot
🔸/donate: ¿cómo puedes colaborar con el mantenimiento de este bot?''')

def about(update, context): #/about command
    context.bot.sendMessage(chat_id=update.effective_chat.id, parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True, text='''
🚍*Arriva Bus Bot*🚍 es un bot no oficial para consultar las paradas y autobuses de la red de autobuses de Arriva desde Telegram. Se trata de un proyecto personal escrito en Python, de código abierto y sin ánimo de lucro.

*La información proporcionada por este bot puede no ser exacta al 100%* por motivos técnicos propios o ajenos, por lo que su uso no ofrece ninguna garantía.

Creado en Ferrol con ❤️, [Python](https://www.python.org/), [python-telegram-bot](https://python-telegram-bot.org/), [SQLite](https://sqlite.org/) y otras fantásticas herramientas y librerías. Inspirado en [VigoBusBot](https://t.me/vigobusbot).
😺[Repositorio GitHub del proyecto](https://github.com/peprolinbot/arrivabus-telegram-bot)

☕️¡Ayuda a mantener este bot en funcionamiento! /donate

_Este proyecto no cuenta con soporte de, no está afiliado con, mantenido por, patrocinado por ni de cualquier otra manera oficialmente conectado con la compañía Arriva o DB._''')

def donate(update, context):
    context.bot.sendMessage(chat_id=update.effective_chat.id, parse_mode=telegram.ParseMode.MARKDOWN, disable_web_page_preview=True, text='''
☕️¡Se necesitan donaciones!☕️
Al contrario que muchas de las aplicaciones para móvil que existen para ver los horarios de los autobuses, los bots de Telegram necesitan funcionar en un servidor de forma constante para que puedan ser utilizados por el público.
Además, ciertas aplicaciones no oficiales, sin sufrir ningún gasto en servidores ni mantenimiento, contienen anuncios y publicidad embebida, que este bot no incluye de ninguna de sus maneras.

Cualquier aportación es de gran ayuda para sufragar el coste que supone mantener el servidor y, por tanto, el bot en funcionamiento, y así mantener este y otros proyectos a flote.
😊¡Gracias!
[PayPal](https://www.paypal.me/peprolinbot)
[BuyMeACofee](https://www.buymeacoffee.com/peprolinbot)
    ''')

def result(update, context): #/result command
    values=mainDb.getExpeditionValues(update.effective_chat.id)
    if values == None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="❌No se espicificó la ruta. Hazlo con el menú del teclado o mandandome su nombre. Para más información manda /help") 
        return
    if len(values) == 3:
        values[2] = datetime.strptime(values[2], "%d-%m-%Y")
    expeditionsJson = arrivapi.getExpeditions(*values)
    mainDb.removeExpedition(update.effective_chat.id) 
    if expeditionsJson == None:
        context.bot.sendMessage(chat_id=update.effective_chat.id, text="❌No se encontró ninguna ruta con los parámetros especificados\U0001F62D")
    else:
        result = generateExpeditionsText(expeditionsJson, "ida")
        for msg in result:
            context.bot.sendMessage(chat_id=update.effective_chat.id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)
        result = generateExpeditionsText(expeditionsJson, "vuelta")
        for msg in result:
            context.bot.sendMessage(chat_id=update.effective_chat.id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)

def textManager(update, context):
    stop = arrivapi.checkStopByName(update.message.text)
    if stop != False:
        selectStop(update, context, update.message.text)
        if stop["parada"] in mainDb.getFavoriteStops(update.effective_chat.id):
            favBtnText = "Quitar de favoritos❌"
            favBtnCallbackData = "rmFavorite;" + update.message.text
        else:
            favBtnText = "Añadir a favoritos♥️"
            favBtnCallbackData = "addFavorite;" + update.message.text
        keyboard = [[InlineKeyboardButton(favBtnText, callback_data=favBtnCallbackData)]]#[InlineKeyboardButton("Seleccionar parada", callback_data="select;" + update.message.text)], 
        keyboardObj = InlineKeyboardMarkup(keyboard)
        bot.send_message(chat_id=update.effective_chat.id, text="❓¿Quieres "+ favBtnText.lower()[:-1] +" esta parada?", reply_markup=keyboardObj)
    else:
        search(update, context, update.message.text)

def callbackQueriesHandlerFunc(update, context):
    query = update.callback_query
    query.answer()
    action = query.data.split(";")[0]
    arg = query.data.replace(action+';', '', 1)
    if action == "select":
        selectStop(update, context, arg)
    elif action == "addFavorite":
        addFavorite(update, context, arg)
        query.edit_message_text(text="OK")
    elif action == "rmFavorite":
        rmFavorite(update, context, arg)
        query.edit_message_text(text="OK")

def search(update, context, request=None):
    if request == None:
        request = update.message.text.split()[1:]
    else:
        request = request.split() 
    stops = arrivapi.getStops()
    results = []
    for stop in stops:
        for word in request:
            if word.lower() in stop['nombre'].lower() or word.lower() in stop['nom_web'].lower():
                results.append(stop['nom_web'])
    if results == []:
        bot.send_message(chat_id=update.effective_chat.id, text="❌No se encontraron paradas para tu búsqueda\U0001F62D")
        return
    keyboard = [[KeyboardButton("⬅️Atrás")]]
    for buttonText in results:
        keyboard += [[KeyboardButton(buttonText)]]
    resultsMenu = simpleMenu(keyboard, "✅Estos son los resultados de tu búsqueda")
    resultsMenu.send(update, context)
    
    

def selectStop(update, context, text=None):
    if text == None:
        text = update.message.text.split()[1:]
        text= ' '.join(text)
    insertedInto = mainDb.autoInsertToExpedition(update.effective_chat.id, text)
    if insertedInto == "originStopId":
        bot.send_message(chat_id=update.effective_chat.id, text="✅Parada fijada como origen.")
    elif insertedInto == "destStopId":
        bot.send_message(chat_id=update.effective_chat.id, text="✅Parada fijada como destino. Si no quieres las paradas para el día de hoy, selecciona la fecha con /setDate Día-mes-año. Usa /result o el botón \"Resultados\" para ver los viajes disponibles.")
    elif insertedInto == "date":
        mainDb.removeExpedition(update.effective_chat.id)
        bot.send_message(chat_id=update.effective_chat.id, text="❌Ya has puesto todos los valores. Para las fechas se usa /setDate")

def selectDate(update, context, date=None):
    if date == None:
        date = update.message.text.split()[1:]
        date= ' '.join(date)
    try:
        insertedInto = mainDb.autoInsertToExpedition(update.effective_chat.id, date)
    except Exception:
        bot.send_message(chat_id=update.effective_chat.id, text="❌Vuelve a intentarlo después de haber puesto una prada de origen y una de destino.")
        return
    if insertedInto == "date":
        bot.send_message(chat_id=update.effective_chat.id, text="✅Fecha fijada. Usa /result o el botón \"Resultados\" para ver los viajes disponibles")
    else:
        mainDb.removeExpedition(update.effective_chat.id)
        bot.send_message(chat_id=update.effective_chat.id, text="❌Vuelve a intentarlo después de haber puesto una prada de origen y una de destino.")

def addFavorite(update, context, stopName=None):
    if stopName == None:
        stopName = update.message.text.split()[1:]
        stopName= ' '.join(stopName)
    stopId = arrivapi.nameToStopId(stopName)
    mainDb.insertNewfavoriteStop(update.effective_chat.id, stopId)
    bot.send_message(chat_id=update.effective_chat.id, text="✅Parada añadida a favoritos.")

def rmFavorite(update, context, stopName=None):
    if stopName == None:
        stopName = update.message.text.split()[1:]
        stopName= ' '.join(stopName)
    stopId = arrivapi.nameToStopId(stopName)
    mainDb.deleteFavoriteStop(update.effective_chat.id, stopId)
    bot.send_message(chat_id=update.effective_chat.id, text="✅Parada quitada de favoritos.")

def eraseAll(update, context):
    mainDb.deleteEverythingFromUser(update.effective_chat.id)
    bot.send_message(chat_id=update.effective_chat.id, text="✅Borrado. Ya no sé nada sobre tí.")

#Defining handlers
startHandler = CommandHandler('start', start)  
helpHandler = CommandHandler('help', help)
aboutHandler = CommandHandler('about', about)
donateHandler = CommandHandler('donate', donate)
eraseAllHandler = CommandHandler('borrar_todo', eraseAll)
# selectStopHandler = CommandHandler('select', selectStop)
selectDateHandler = CommandHandler('setDate', selectDate)
# addFavoriteHandler = CommandHandler('addFavorite', addFavorite)
# rmFavoriteHandler = CommandHandler('rmFavorite', rmFavorite)
searchHandler = CommandHandler('search', search)
resultHandler = CommandHandler('result', result)

btnSearchBusesHandler = MessageHandler(Filters.regex(r"^"+"🔍Resultados"+"$"), result)
btnFavoriteStopsHandler = MessageHandler(Filters.regex(r"^"+"♥️Paradas favoritas"+"$"), allFavoriteStopsMenu.send)
btnBackHandler = MessageHandler(Filters.regex(r"^"+"⬅️Atrás"+"$"), mainMenu.send)
allMsgHandler = MessageHandler(Filters.all, textManager)

callbackQueriesHandler = CallbackQueryHandler(callbackQueriesHandlerFunc)

dispatcher = updater.dispatcher

import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                     level=logging.INFO)

#Adding handlers
dispatcher.add_handler(startHandler)
dispatcher.add_handler(helpHandler)  
dispatcher.add_handler(aboutHandler)
dispatcher.add_handler(donateHandler)
# dispatcher.add_handler(selectStopHandler)
dispatcher.add_handler(selectDateHandler)
# dispatcher.add_handler(addFavoriteHandler)
# dispatcher.add_handler(rmFavoriteHandler)
dispatcher.add_handler(searchHandler)
dispatcher.add_handler(resultHandler)
dispatcher.add_handler(btnSearchBusesHandler)
dispatcher.add_handler(btnFavoriteStopsHandler)
dispatcher.add_handler(btnBackHandler)
dispatcher.add_handler(allMsgHandler)
dispatcher.add_handler(callbackQueriesHandler)

updater.start_polling()
