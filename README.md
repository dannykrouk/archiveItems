Capabilities
This script allows for the "archiving" (export/download) of select items (of specific types) from a Web GIS
Those items successfully archived can be deleted
A configuration file and an Inventory Excel document are the inputs that control the logic

Instructions
1. Run GIS Enterprise Reporter (https://community.esri.com/t5/implementing-arcgis-blog/introducing-the-gis-enterprise-reporter/ba-p/1161310), or something, to generate a content inventory
2. Add two columns to the Inventory sheet, one to indicate archiving and one to indicate deleting (only valid in the case that the item is successfully archived)
3. Populate the columns with 'yes' and 'no' (leave none empty) to indicate what you want archived and which of those should be deleted
4. Edit the config.ini file to point to:
      a. Your AGOL Organization or AGE (https://developers.arcgis.com/python/latest/guide/working-with-different-authentication-schemes/#built-in-users) 
      b. A username, password, and the user's id (which can be found in the Sharing API information about that user)
      c. The full path to the Excel inventory file
      d. The location to put the archive output ("data_dmp") ... the directory must already exist 
5. Review the variables section below to 
6. Execute following a pattern like this: "C:\Program Files\ArcGIS\Server\framework\runtime\ArcGIS\bin\Python\Scripts\propy.bat" "archiveItems.py"
