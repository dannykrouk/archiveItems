############################################################################################
################## Name: Archive Items Script ##############################################
################## Author: Ayyaz Mahmood Paracha ###########################################
################## Date: 9th JULY 2024 #####################################################
################## Minor edits: Danny Krouk ################################################
################## Date: 1 Nov 2024 ########################################################
############################################################################################

# Capabilities
# This script allows for the "archiving" (export/download) of select items (of specific types) from a Web GIS
# Those items successfully archived can be deleted
# A configuration file and an Inventory Excel document are the inputs that control the logic

# Instructions
# 1. Run GIS Enterprise Reporter (https://community.esri.com/t5/implementing-arcgis-blog/introducing-the-gis-enterprise-reporter/ba-p/1161310), or something, to generate a content inventory
# 2. Add two columns to the Inventory sheet, one to indicate archiving and one to indicate deleting (only valid in the case that the item is successfully archived)
# 3. Populate the columns with 'yes' and 'no' (leave none empty) to indicate what you want archived and which of those should be deleted
# 4. Edit the config.ini file to point to:
#       a. Your AGOL Organization or AGE (https://developers.arcgis.com/python/latest/guide/working-with-different-authentication-schemes/#built-in-users) 
#       b. A username, password, and the user's id (which can be found in the Sharing API information about that user)
#       c. The full path to the Excel inventory file
#       d. The location to put the archive output ("data_dmp") ... the directory must already exist 
# 5. Review the variables section below to 
# 5. Execute following a pattern like this: "C:\Program Files\ArcGIS\Server\framework\runtime\ArcGIS\bin\Python\Scripts\propy.bat" "archiveItems.py"


import os, time, configparser, logging, sys, openpyxl, requests, json, datetime, tempfile, csv
from arcgis.gis import GIS
from arcgis.gis import User
timeStart = time.time()

############################## VARIABLES ##################################################
# Other than those in the config.ini...

taskname = 'Archive_Items' # Just used in the name of the log file
excelSheetName = 'Inventory' # The name of the sheet in the Excel that has the inventory and columns with flags for archiving and deleting

# The values to indicate what should be archived and deleted
archiveFlag = 'yes' # This is the text value to put in the archiveFlagColumn to indicate which items should be archived.  NO ROW VALUE MAY BE EMPTY.  So, you may put any other text value in the rows you do not wish to archive (like 'no')
deleteFlag = 'yes' # This is the text value to put in the deleteFlagColumn to indicate which successfully archived items should be deleted. NO ROW VALUE MAY BE EMPTY.  So, you may put any other text value in the rows you do not wish to delete (like 'no')

# These column numbers that have the information to drive the logic of the script
# The following three typically do not need any attention if you are using GIS Enterprise Reporter output
idColumnNumber = 1 # first column in sheet *is* the id of the item
ownerColumnNumber = 2 # second column in sheet *is* owner of the item
typeColumnNumber = 8 # eigth column in sheet *is* type of the item 
# The following two depend on where you added the columns
archiveFlagColumnNumber = 11 # add a column ("archiveFlag", if you like) to place the 'archive' flag.  This integer reflects its order in the columns in the sheet (first column is 1)
deleteFlagColumnNumber = 12 # add a column ("deleteFlag", if you like)to place the 'delete' flag.  This integer reflects its order in the columns in the sheet (first column is 1)

############################## CONSTANTS ##################################################
# These are lists of the types that are eligible for archiving.  There are different collections because different types require different archiving logic
# You should leave these lists alone
lst_file_types = ['File Geodatabase','Service Definition','Shapefile','CSV','Mobile Map Package','Microsoft Word','Project Package','Notebook', 'PDF','CSV Collection','Tile Package']
lst_export_services = ['Feature Service']
lst_other_services = ['Image Service','Scene Service']
lst_data_apps = ['Web Map','Web Scene','Web Mapping Application', 'Dashboard', 'Feature Collection']
lst_other_apps = ['Form','Web Experience','StoryMap']


############################## CREATE LOG FILE ##############################################
WorkSpaceFolder = os.path.dirname(__file__)
log_file_name = taskname + "_" + str(time.strftime("%Hh%Mm%Ss",time.gmtime(timeStart))) + ".txt"
log_file = log_file = os.path.join(WorkSpaceFolder, log_file_name)
handlers = [logging.FileHandler(log_file), logging.StreamHandler()]
# Configuring logging settings
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S',
    level=logging.INFO,
    handlers=handlers)

############################## READ INPUT ARGUMENTS (CONFIG FILE) ###########################
Config = configparser.ConfigParser()
Config.read(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.ini"))

sourcePortal = Config.get('source', 'sourceAgol')
sourceUserName = Config.get('source', 'sourceUserName')
sourcePassword = Config.get('source', 'sourcePassword')
sourceUserId = Config.get('source', 'sourceUserID')
inputExcelFile = Config.get('source', 'inputExcelFile')
data_dmp = Config.get('source', 'data_dmp')

logging.info("source Portal: " + sourcePortal)
logging.info("source UserName: " + sourceUserName)
logging.info("source UserId: "+ sourceUserId)
logging.info("Data backup location: "+ data_dmp)
logging.info("Input Reference Excel File Name: "+ inputExcelFile)

if os.path.exists(inputExcelFile):
    logging.info("Input Reference Excel File exists. Continuing ...")
else:
    logging.error("Input Reference Excel File does not exist. Exiting.")
    sys.exit(0)


#################### CONNECT WITH SOURCE PORTAL ##############################################
source = GIS(sourcePortal, sourceUserName, sourcePassword, verify_cert = False, expiration = 9999)
logging.info("Connected to Source AGOL " + sourcePortal + " as " + sourceUserName)
SourceToken = source._con.token
logging.info("The Source Generated Token is " + SourceToken)

################### VERIFY SOURCE PORTAL ######################################################
SourceTokenVerifyUrl = sourcePortal + 'sharing/rest/community/users/' + sourceUserName + '?f=json&token=' + SourceToken
logging.info("Source User Verify URL --> " + SourceTokenVerifyUrl)
responseSource = requests.get(SourceTokenVerifyUrl)
json_source_response = json.loads(responseSource.text)
if not "error" in json_source_response:
    Obtained_Source_ID = json_source_response["id"]
    if Obtained_Source_ID == sourceUserId:
        logging.info("The user ID in the portal matches the configured user id. Continuing ...")
    else:
        logging.error("The user id in the portal " + Obtained_Source_ID + " is not the same as in Configured file " + sourceUserId + " . Exiting.")
        sys.exit(0)
else:
    logging.error("Error in Source ID Verification. " + json_source_response + ". Exiting.")
    sys.exit(0)


#################### TO READ EXCEL FILE ######################################################

logging.info("Loading Excel and sheet ...")
wb_target = openpyxl.load_workbook(inputExcelFile) # Content Excel from GIS Enterprise Reporter
Inventory = wb_target[excelSheetName] # Inventory sheet in Content Excel
inventory_row = Inventory.max_row

logging.info("Processing rows in sheet ... ")
for i in range(2, inventory_row + 1):
    
    # Get the values of interest from the Inventory row
    SourceItem_Id = Inventory.cell(row = i, column = idColumnNumber ).value 
    SourceItem_Owner = Inventory.cell(row = i, column =  ownerColumnNumber).value 
    SourceItem_ArchiveFlag_Value = Inventory.cell(row = i, column = archiveFlagColumnNumber).value 
    SourceItem_DeleteFlag_Value = Inventory.cell(row = i, column = deleteFlagColumnNumber).value 
    SourceItem_Type = Inventory.cell(row = i, column = typeColumnNumber).value 
    
    # if the item is flagged for archiving ...
    archiveFlagValue = SourceItem_ArchiveFlag_Value
    if archiveFlagValue is not None:
        if archiveFlagValue.lower() == archiveFlag:
            user_folder = os.path.join(data_dmp,SourceItem_Owner)
            if not os.path.exists(user_folder):
                os.mkdir(user_folder)
            item_folder = os.path.join(user_folder,SourceItem_Id)
            if not os.path.exists(item_folder):
                os.mkdir(item_folder)
                if SourceItem_Type in lst_file_types:
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        # archive
                        data_file = Source_item.download(item_folder)
                        # delete, if indicated
                        try:
                            if SourceItem_DeleteFlag_Value == deleteFlag:
                                Source_item.delete()
                        except Exception as del_ex:
                            logging.error("\tError deleting id: " + SourceItem_Id)

                elif SourceItem_Type in lst_data_apps:
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        # archive 
                        data_file = None
                        text = Source_item.get_data()
                        text_str = json.dumps(text)
                        TargetJSONFile = os.path.join(item_folder,SourceItem_Type + ".json")
                        f = open(TargetJSONFile, "a")
                        json.dump(text_str, f)
                        f.close()
                        # delete, if indicated 
                        try:
                            if SourceItem_DeleteFlag_Value == deleteFlag:
                                Source_item.delete()
                        except Exception as del_ex:
                            logging.error("\tError deleting id: " + SourceItem_Id)

                elif SourceItem_Type in lst_export_services:
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        try:
                            
                            # archive
                            exported_folder_item = Source_item.export(SourceItem_Id, 'File Geodatabase', wait=True) 
                            #logging.info("The id of extracted folder --> " + exported_folder_item.id + ". Take a break of 15 seconds")
                            logging.info("The id of extracted folder --> " + exported_folder_item.id + ".")
                            #time.sleep(15)
                            logging.info("The data is downloading")
                            downloaded_zip_file=exported_folder_item.download(save_path=item_folder)
                            #logging.info("The data is downloaded. Take a break of 1 minute.")
                            logging.info("The data is downloaded.")
                            # delete, if indicated
                            try:
                                if SourceItem_DeleteFlag_Value == deleteFlag:
                                    Source_item.delete()
                            except Exception as del_ex:
                                logging.error("\tError deleting id: " + SourceItem_Id)
                                
                        except Exception as copy_ex:
                            logging.error("\tError exporting " + Source_item.title)
                            logging.error("\t" + str(copy_ex))
                            error_data = {
                                    "itemname": Source_item.title,
                                    "itemid": SourceItem_Id,
                                    "download_error": str(copy_ex)
                                    }
                            TargetJSONFile = os.path.join(item_folder,SourceItem_Type + "_error.json")
                            f = open(TargetJSONFile, "a")
                            json.dump(error_data, f, indent=4)
                            f.close()
                
                elif SourceItem_Type in lst_other_services:
                    # These types are not archivable by this script
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        error_data = {
                            "itemname": Source_item.title,
                            "itemid": SourceItem_Id,
                            "download_error": "Unable to export this format. Please find source files for this service"
                            }
                        TargetJSONFile = os.path.join(item_folder,SourceItem_Type + "_error.json")
                        f = open(TargetJSONFile, "a")
                        json.dump(error_data, f, indent=4)
                        f.close()

                elif SourceItem_Type in lst_other_apps:
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        # archive 
                        data_file = None
                        text = Source_item.get_data()
                        text_str = json.dumps(text)
                        TargetJSONFile = os.path.join(item_folder,SourceItem_Type + ".json")
                        f = open(TargetJSONFile, "a")
                        json.dump(text_str, f)
                        f.close()
                        if SourceItem_Type == 'Form':
                            dict_relations = {}
                            ind = 0
                            rel_items_data = Source_item.related_items("Survey2Data", "forward")
                            for rel_item in rel_items_data:
                                rel_item_id = rel_item.id
                                data_file = rel_item.download(item_folder)
                            rel_items_services = Source_item.related_items("Survey2Service", "forward")
                            for rel_item in rel_items_services:
                                rel_item_id = rel_item.id
                                ind = ind + 1
                                dict_relations[str(ind) + " relation ITEM ID for this form is "] = rel_item_id
                                dict_relations[str(ind) + " relation ITEM URL for this form is "] = rel_item.url
                            TargetJSONFile = os.path.join(item_folder,SourceItem_Type + "_rel_services.json")

                            f = open(TargetJSONFile, "a")
                            json.dump(dict_relations, f, indent=4)
                            f.close()
                        else:
                            extracted_folder = Source_item.resources.export(item_folder)
                        # delete, if indicated
                        try:
                            if SourceItem_DeleteFlag_Value == deleteFlag:
                                Source_item.delete()
                        except Exception as del_ex:
                            logging.error("\tError deleting id: " + SourceItem_Id)
                
                else:
                    # not archivable by this script 
                    Source_item = source.content.get(SourceItem_Id)
                    if Source_item is not None:
                        error_data = {
                            "itemname": Source_item.title,
                            "itemid": SourceItem_Id,
                            "download_error": "Export operation not supported for this data type"
                            }
                        TargetJSONFile = os.path.join(item_folder,SourceItem_Type + "_error.json")
                        f = open(TargetJSONFile, "a")
                        json.dump(error_data, f, indent=4)
                        f.close()
                
                