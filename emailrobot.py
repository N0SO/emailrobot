#!/usr/bin/env python3
"""
emailrobot - Process Missouri QSO Party log files received as 
             e-mail attachments.

This program will read e-mail from the e-mail account defined in 
robotconfig.py, then process the attached files. It calls 
cabrillofilter.py to verify the integrety of the Cabrillo format
log file, and to pull data about the station and submitter for
inclusion in the MOQP database file defined in robotconfig.py.

This script is intended to be called from the cron daemon to periodically
check for new logs, but could be triggered from a web browser as well.

Update History:
* Sat Mar 26 2022 Mike Heitmann, N0SO <n0so@arrl.net>
- V2.0.0 - Support for Python SQL functions added to w0ma.org server.
-          This app was refactored to eliminate the need for calling
-          a PHP script to perform the SQL functions.
-          Also, fixes for issues #11, #12, #13, #14, and a partial
-          for #15. 15 could use some refinement for further sorting
-          of excel and pdf docs.

"""
from imap_tools import MailBox, AND
import pymysql, datetime
from robotconfig import *
from cabrillofilter import *
#from cabrillolog import logfile
#from robotmail import *
#from email.mime.text import MIMEText

VERSION = '3.0.0'
ERRORINLOG = "Error! attached log is NOT a plain text file!"
CTYPES = ['text/x-log',
          'application/octet-stream',
          'text/plain','application/pdf',
          'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']

class emailRobot():

   def __init__(self, auto=False):
      if(auto):
          self.main()
     
   def getVersion(self):
      return self.VERSION
      
      
   def createDBEntry(self, status, msgparts, logdict, filename):
       cnx = pymysql.connect(user=dbusername, password=dbpassword, 
                             host=dbhostname, database=dbname)
       timestring = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S")
       if msgparts.reply_to:
           email = msgparts.reply_to
       else:
           email = msgparts.from_

       if 'WEB' in msgparts.subject:
           rcvd_by = 'WEB'
       else:
           rcvd_by = 'EMAIL'

       curser=cnx.cursor()
       query = """INSERT INTO logs_received (STA_CALL,
	      			             OP_NAME,
	      			             EMAIL,
	                         RECEIVED_BY,
	                         FILENAME,
	                         DATE_REC,
	                         EMAILSUBJ)	
	       
	             VALUES (%s,%s,%s,%s,%s,%s,%s)"""
       params = (logdict['CALLSIGN'],
	            logdict['NAME'],
	            email,
	            rcvd_by,
	            filename,
	            timestring,
	            msgparts.subject)
	                    
       #print('query = %s'%(query))
       curser.execute(query, params)
       cnx.commit()
       cnx.close()

   def saveFile(self, fileData, callsign):
       cabFilter = CabrilloFilter()
       logcall=cabFilter.stripCallsign(callsign)
       if len(logcall)>=3:
           filename= logready+logcall.upper()+'.LOG'
           #print(f'filename={filename}')
           with open(filename, 'w') as f:
               f.write(fileData)
       else:
           print('*** No callsign in CABRILLO header ***')
           filename = None
       return filename

   def processFile(self, att):
       logHeader = None
       fileName = None
       if att.content_type == 'application/octet-stream':
           cabFilter = CabrilloFilter()
           logdata=att.payload
           logdata = logdata.decode('utf-8')
           #print(logdata)
           logdict = cabFilter.main(logdata)
           if "HEADER" in logdict:
               logHeader = logdict["HEADER"]
               fileName = self.saveFile(logdata,logHeader['CALLSIGN'])
               
       return logHeader, fileName

   def main(self):
       status = False
       #mailSender = robotMail() # For sending results to recipients and 
       with MailBox(imap_host, port=993).login(\
                      imap_user, 
                      imap_pass, 
                      initial_folder='INBOX') as mailbox:
           # Iterate over all unseen messages
           for msg in mailbox.fetch(AND(seen=False)):
               print(f'--- robotmail processing message uid {msg.uid} at {datetime.datetime.utcnow().strftime("%Y-%m-%d-%H-%M-%S-%f")} ---')
               print(f'date: {msg.date},from: {msg.from_values},reply to: {msg.reply_to_values},subject:{msg.subject}...')

               fc = len(msg.attachments)
               if fc > 0:
                   atcount = 1
                   files = []
                   filestat = False
                   print(f'Attachment count: {fc}')
                   for att in msg.attachments:
                       files.append(att.filename)
                       # Process file here
                       logHead, fileName = self.processFile(att)
                       if logHead and fileName:
                           filefmt="Cabrillo "
                           status = True
                       else:
                           filefmt="*** NOT Cabrillo ***"
                           status = False
                       print(f'Attachment {atcount}: Name:{att.filename}, type: {att.content_type}, {filefmt} file') 
                       if fileName:
                           print(f'Attachemnt {atcount} saved as {fileName}.')
                       else:
                           print(f'Attachment {atcount} *** NOT SAVED ***, check original e-mail message.')
                       self.createDBEntry(status, msg, logHead, fileName)
                       atcount += 1
               else:
                   print('*** No attachments, nothing saved ***')
                   status = False
               if status:
                   print('+++ Log Entry Accepted +++')
               else:
                   print('*** Log Entry REJECTED ***')

       return status

if __name__=='__main__':
    mailbot = emailRobot(True)
