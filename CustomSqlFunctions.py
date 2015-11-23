'''Create Functions that can be called from SQLite'''
import os

def RegisterFunctions(dbh):
	'''Register your created functions here'''
	dbh.create_function('basename',1,Basename)
	
def Basename(filename):
	'''Get the base name of a fullname string'''
	try:
		value = os.path.basename(filename)
	except:
		value = filename
	
	return value