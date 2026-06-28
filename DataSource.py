from pathlib import Path
from decimal import Decimal
import json
import csv
import io
from zipfile import ZipFile
import pandas as pd 
import requests

class DataSource:
    """

    Object that represents a data source and provides methods for interacting with it.

    Paramters: 
        name (str): The name of the data source.
        dataUrl (function): A function that generates the URL for the API request to get the data.
        metadataUrl (function): A function that generates the URL for the API request to get the metadata.
        normalize (function): A function that converts the API response into a pandas DataFrame or Series.
        checkRequest (function, optional): A function that checks the API request for error flags. Defaults to False.
        dtype (type, optional): The type of the normalized data output. Defaults to pd.DataFrame.
        data_folder (str, optional): The path to the folder where the data will be saved. Defaults to False.

    Methods:
        dataUrl(parameters): Generates the URL for the API request to get the data.
        metadataUrl(parameters): Generates the URL for the API request to get the metadata.
        saveToCache(url, response): Saves API responses to the cache.
        loadFromCache(key): Loads API responses from the cache.
        get(url, stream=False, timeout=120): Performs a GET request to the API.
        post(url, body, timeout=30): Performs a POST request to the API.
        checkRequest(response): Checks the API request for error flags.
        normalize(rawData, metadata=False): Converts the API response into a pandas DataFrame or Series.
        saveData(data): Saves a pandas DataFrame or Series to a CSV file.
        loadData(file_title): Loads a pandas DataFrame or Series from a CSV file.
        printSavedData(): Prints a list of all the CSV files in the data folder.

    """
    catm = "CATM_"

    def __init__(self, name, dataUrl, metadataUrl, normalize, checkRequest=False, dtype=pd.DataFrame, data_folder=False):
    

        ## Set the name of the DataSource
        if type(name) is str:
            self.name = name.replace(" ","_")
        else:
            raise ValueError("The name argument must be a string.")


        ## Set the data type of the normalized data output
        if (dtype is pd.DataFrame) or (dtype is  pd.Series):
            self.dtype = dtype
        else:
            raise ValueError("The name argument must be a pandas DataFrame or Series.")


        ## Initialize the instance attributes that contain the necessary wrapper functions:
        # The function that makes the data request via the API.
        if callable(dataUrl):
            self._dataUrl = dataUrl
        else:
            raise ValueError("The requestFunction argument must be a function.")
        # The function that makes the metadata request via the API.
        if callable(metadataUrl):
            self._metadataUrl = metadataUrl
        else:
            raise ValueError("The requestFunction argument must be a function.")
        # Initialize checkRequest function 
        if not checkRequest:
            self._checkRequest = None
        elif callable(checkRequest):
            self._checkRequest = checkRequest
        else:
            raise ValueError("The requestFunction argument must be a function.")
        # The function that converts the response into a pandas DataFrame or Series. 
        if callable(normalize):
            self._normalize = normalize
        else:
            raise ValueError("The requestFunction argument must be a function.")
        

         ## Setup the data_folder & the cache 
        if data_folder: # Create the data folder at the path specified in the cache_path argument
            self.data_folder = Path(data_folder) / self.name
            self.data_folder.mkdir(parents=True, exist_ok=True)
        else: # Create a data folder path in the same folder where the current python file is located
            self.data_folder = Path(__file__).resolve().parent / self.name
            self.data_folder.mkdir(parents=True, exist_ok=True)  
        # Create the cache folder for get requests
        self.cache_folder = self.data_folder / "Cache"
        self.cache_folder.mkdir(exist_ok=True) 


        ## Initialize dictionary of saved DataFrames and Series 
        self.dataLibrary = {}
        for file in self.data_folder.iterdir():
            if file.name.startswith("CATM_") and (file.name.endswith(".csv")):
                if "_D" in file.name:
                    self.dataLibrary[file.name] = pd.DataFrame
                elif "_S" in file.name:
                    self.dataLibrary[file.name] = pd.Series
        

        ## Initialize dictionary of cached API requests and posts
        self.APICache = {}
        for file in self.cache_folder.iterdir():
            if file.name.startswith("CATM_") and (file.name.endswith(".json") or file.name.endswith(".zip")):
                    url = file.name[5:]
                    self.APICache[url] = self.cache_folder / file.name
       
    def dataUrl(self, paramters):
        """
        Creates the API URL for the data endpoint.

        Parameters:
            parameters (dict): A dictionary containing the parameters for the data request.
        Returns:
            str: The URL for the data endpoint.
        """
        ## Handle type error for the parameters argument
        if type(paramters) is not dict:
            raise TypeError("The paramters argument of the request function must be formatted as a Python dictionary object.")
        ## Call the dataUrl function on the request that was initialized
        return self._dataUrl(paramters)
    
    def metadataUrl(self, parameters):
        """
        Creates the API URL for the metadata endpoint.

        Parameters:
            parameters (dict): A dictionary containing the parameters for the metadata request.

        Returns:
            str: The URL for the metadata endpoint.
        """
        ## Handle type error for the parameters argument
        if type(parameters) is not dict: 
            raise TypeError("The paramters argument of the request function must be formatted as a Python dictionary object.")
        ## Call the metadataUrl function on the request that was initialized
        return self._metadataUrl(parameters)

    def saveToCache(self, url, response):
        """
        Saves the API response to the cache.

        Parameters:
            url (str): The URL of the API request.
            response (dict or bytes): The API response to be saved.

        Returns:
            None
        """
        # Create the title for the cached version
        title = DataSource.catm+url
        file_path = self.cache_folder / title.replace("/", "-").replace(":","")

        # Save the file to the cache
        if type(response) is dict:
            file_path = Path(f"{file_path}.json")
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(response, file)
        elif type(response) is bytes:
            file_path = Path(file_path)
            with open(file_path, "wb") as file:
                file.write(response)
            
        # Add the file to the Cache dictionary
        self.APICache[url] = file_path

    def loadFromCache(self, key):
        """
        Loads the API response from the cache.

        Parameters:
            key (str): The key of the cached API response, which is the URL of the API request with slashes and colons replaced by hyphens.

        Returns:
            dict or bytes: The cached API response, as a dictionary if the response is JSON, or as bytes if the response is a zip file.
        """
        # Create the title for the cached version
        file_path = self.APICache[key]

        # Load the file from the cache
        if file_path.suffix == ".zip":
            with open(file_path, 'rb') as file:
                response = file.read()
        elif file_path.suffix == ".json":
            with open(file_path, 'r', encoding="utf-8") as file:
                response = json.load(file)
        return response
        
    def get(self, url, stream=False, timeout=120):
        """
        Performs a GET request to the API.

        Parameters:
            url (str): The URL of the API request.
            stream (bool, optional): Whether to stream the response. Defaults to False.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 120.
        
        Returns:
            dict or bytes: The API response, as a dictionary if the response is JSON, or as bytes if the response is a zip file.
        """

        ## Check if the request has been made and saved to the cache, if so return the cached version of the request
        key = url.replace("/","-").replace(":","")
        if key in self.APICache:
            return self.loadFromCache(key)

        # If it has not already been cached, perform the API request
        else:
            response = requests.get(url, stream=stream, timeout=timeout)
            response.raise_for_status()
            content_type = response.headers.get('Content-Type', '')

            # Handle the response based on its content type and save it to the cache
            if 'application/json' in content_type:
                payload = response.json()
                self.saveToCache(url, payload)
            elif 'application/zip' in content_type:
                payload = response.content
                self.saveToCache(url, payload)

            return payload 

    def post(self, url, body, timeout=30): 
        """
        Performs a POST request to the API.

        Parameters:
            url (str): The URL of the API request.
            body (dict): The body of the API request.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 30
        
        Returns:
            dict: The API response as a dictionary. (No handling for zip files.)
        """
        ## Perform the API request
        response = requests.post(url, json=body, timeout=timeout)
        response.raise_for_status()
        payload = response.json()      
        return payload
    
    def checkRequest(self, response):
        """
        Checks the API request for error flags.

        Parameters:
            response (dict): The API response to be checked.
        
        Returns:
            None
        """

        ## Call the checkRequest function on the request if it was initialized
        if self._checkRequest:
            self._checkRequest(response)

    def normalize(self, rawData, metadata=False):
        """
        Converts the API response into a pandas DataFrame or Series.

        Parameters:
            rawData (dict or bytes): The API response to be normalized.
            metadata (dict, optional): The metadata for the API response. Defaults to False.
        
        Returns:   
            pd.DataFrame or pd.Series: The normalized data as a pandas DataFrame or Series.
        """
        return self._normalize(rawData, metadata)

    def saveData(self, data):
        """
        Saves the provided pandas DataFrame or Series data to a CSV file.

        Parameters:
            data (pd.DataFrame or pd.Series): The data to be saved.
        
        Returns: 
            None
        """
        # Save a pandas DataFrame to CSV
        if type(data) is pd.DataFrame:
            table_name = data.attrs["name"].replace(" ","_")
            file_name = DataSource.catm+table_name+"_D.csv"
            with open(self.data_folder / file_name, "w", newline='') as file:
                file.write(f"{table_name}\n")
                data.to_csv(file)    
            self.dataLibrary[file_name] = pd.DataFrame  

        # Save a pandas Series to CSV
        elif type(data) is pd.Series:
            series_name = data.name.replace(" ","_")
            file_name = DataSource.catm+series_name+"_S.csv"
            data.to_csv(self.data_folder / file_name)
            self.dataLibrary[file_name] = pd.Series    

        # Throw an error if the data is not a pandas DataFrame and Series    
        else:
            raise ValueError("The data argument must be a pandas DataFrame or Series.")
    
    def loadData(self, file_title):
        """
        Loads a pandas DataFrame or Series from a CSV file.
        
        Parameters:
            file_title (str): The title of the file to be loaded, without the prefix or suffix.
        
        Returns:   
            pd.DataFrame or pd.Series: The loaded data as a pandas DataFrame or Series.
        """
        # Adding the prefix of the filename
        file_name =  DataSource.catm+file_title

        # Check if the file is stored as a DataFrame
        if file_name+"_D.csv" in self.dataLibrary:
            file_name += "_D.csv"
            table = pd.read_csv(self.data_folder/file_name, skiprows=1, converters={0: str}) # REORGANIZE
            index_column = table.columns[0]
            table = table.set_index(index_column)
            if str(index_column).startswith("Unnamed"):
                table.index.name = None
            with open(self.data_folder/file_name, "r", newline='') as file:
                reader = csv.reader(file)
                name = next(reader)[0]
            table.attrs["name"] = name
            return table
        
        # Check if the file is stored as a Series 
        elif file_name+"_S.csv" in self.dataLibrary:
            file_name += "_S.csv"
            series_frame = pd.read_csv(self.data_folder/file_name, converters={0: str})
            index_column = series_frame.columns[0]
            series_frame = series_frame.set_index(index_column)
            if str(index_column).startswith("Unnamed"):
                series_frame.index.name = None
            return series_frame.squeeze("columns")
        
        # Throw an error if the data cannot be found    
        else:
            raise ValueError("The file could not be found in the Data Library.")
       
    def printSavedData(self):
        """
        Prints a list of all the CSV files in the data folder, without the prefix or suffix.

        Parameters:
            None
        
        Returns:
            None
        """
        print("Here is a list of all the CSV files in "+self.data_folder.name+":")

        # Iterate through the contents of the data folder and print the file names w/o prefixes & suffixes 
        i = 1
        for file in self.data_folder.iterdir():
            if file.name.startswith("CATM_") and (file.name.endswith(".csv")):
                print(str(i)+". "+file.name[5:-6])
                i += 1

def checkRequestStatsCan(response):
    """
    Checks the API request for error flags specific to Statistics Canada.

    Parameters: 
        response (dict): The API response to be checked.
    
    Returns:
        None
    """
    # Check if the general API request flags were raised
    response.raise_for_status() 

    # Check if Stats Canada error flags were raised
    payload = response.json()[0]
    if payload.get("status") != "SUCCESS":
        raise ValueError(f"Statistics Canada API request failed: {payload}")

    vector = payload.get("object", {})
    if vector.get("responseStatusCode") != 0:
        raise ValueError(f"Statistics Canada API request failed: {vector}")
def convertFrequencyCode(code):
    """
    Converts a frequency code to its corresponding frequency, time-period, and unit.

    Parameters:
        code (int): The frequency code to be converted.
    
    Returns:
        list: A list containing the frequency, time-period, and unit corresponding to the frequency code
    """
    # Create a dictionary that maps frequency codes to frequencies and time-periods. 
    frequencyCodes = {
        1 : ["Daily", "D", "Days"],
        2 : ["Weekly", "W", "Weeks"],
        4 : ["Biweekly", "2W", "2-Week Peridos"],
        6 : ["Monthly", "M", "Months"],
        7 : ["Bimonthly", "2M", "2-Month Periods"],
        9 : ["Quarterly", "Q", "Quarters"],
        11 : ["Semi-annual", "6M", "6-Month Periods"],
        12 : ["Annual", "Y", "Year"],
        13 : ["Every 2 years", "2Y", "2-Year Periods"],
        14 : ["Every 3 years", "3Y", "3-Year Periods"],
        15 : ["Every 4 years", "4Y", "4-Year Periods"],
        16 : ["Every 5 years", "5Y", "5-Year Periods"],
        17 : ["Every 10 years", "10Y", "10-Year Periods"],
        18 : ["Occasional", "Y", "Occasional (Yearly)"],
        19 : ["Occasional Quarterly", "Q", "Occasional (Quarterly)"],
        20 : ["Occasional Monthly", "M", "Occasional (Monthly)"],
        21 : ["Occasional Daily", "D", "Occasional (Daily)"]
    }

    return frequencyCodes[code] 

def dataUrlStatsCanVectors(parameters):
    """
    Creates the API request URL for fetching data from Statistics Canada vectors.

    Parameters:
        parameters (dict): A dictionary containing the API request parameters.

    Returns:
        str: The API request URL for the data.
    """
    ## Get API request paramters from the dictionary and store them in variables
    vector_id = str(parameters["vector_id"])
    if "," in vector_id:
        raise ValueError("Cannot request more than vector at a time.")
    start_date = parameters["start_date"]
    end_date = parameters["end_date"]

    # Create the API request URL for the data
    api_url = ("https://www150.statcan.gc.ca/t1/wds/rest/"
    "getDataFromVectorByReferencePeriodRange?"
    f"vectorIds=\"{vector_id}\"&"
    f"startRefPeriod={start_date}&"
    f"endReferencePeriod={end_date}")
    return api_url

def metadataUrlStatsCanVectors(parameters):
    """
    Creates the API request URL for fetching metadata from Statistics Canada vectors.

    Parameters:
        parameters (dict): A dictionary containing the API request parameters.

    Returns:
        dict: A dictionary containing the API request URL and body for the metadata.
    """
    ## Get API request paramters from the dictionary and store them in variables
    vector_id = str(parameters["vector_id"])
    if "," in vector_id:
        raise ValueError("Cannot request more than vector at a time.")
    
    # Create the API request URL for the metadata 
    api_metadata_url = "https://www150.statcan.gc.ca/t1/wds/rest/getSeriesInfoFromVector"
    body = [{"vectorId":vector_id}]
    return {"api_metadata_url":api_metadata_url, "body":body}

def normalizeRequestStasCanVectors(dataResponse, metadataResponse):
    """
    Normalizes the API response for Statistics Canada vectors.

    Parameters:
        dataResponse (dict): The API response containing the vector data.
        metadataResponse (dict): The API response containing the vector metadata.

    Returns:
        pd.Series: A pandas Series containing the normalized vector data.
    """
    # Get vector data from response 
    rawData = dataResponse[0]["object"]

    # Populate a list with the raw vector data points
    data_points = []
    data_points.extend(rawData.get("vectorDataPoint", []))

    if not data_points:
        raise ValueError("No vector data points were returned.")
    
    # Get the vector frequency info from the data 
    frequencyCode = data_points[0]["frequencyCode"]
    frequency = convertFrequencyCode(frequencyCode)[0]
    frequencyPeriod = convertFrequencyCode(frequencyCode)[1]
    frequencyUnit = convertFrequencyCode(frequencyCode)[2]

    # Set empty title variable in case no metadata is provided
    title = ""
    if metadataResponse:
            # Get the vector metadata from the response
            rawMetadata = metadataResponse[0]["object"]

            # Get the vector title info from the metadata 
            title = rawMetadata["SeriesTitleEn"].replace(";","; ").rstrip()
            title = title + f" ({frequency})" 
    
    # If vector contains spanned refernce period data, throw error
    if data_points[0]["refPer2"] != "":
        raise ValueError("Need to create handler for spanned reference period data.")

    # Create lists for the pandas Series values and (time) indices
    values = []
    times = []

    # Iterate through the data points in the raw vector data to process and add them to the appropriate list
    for datapoint in data_points:
        # Handle scalar factoring
        value = Decimal(str(datapoint["value"])) * Decimal((10 ** datapoint["scalarFactorCode"]))
        values.append(float(value))
        # Convert time data to pandas Period format
        time = datapoint["refPer"]
        time =  pd.Period(time, freq=frequencyPeriod)
        times.append(time)
    
    # Initialize the pandas Series with the processed vector data
    series = pd.Series(values, index=times, name=title)
    series.index.name = frequencyUnit

    return series
def runStatsCanVectors(ds, vector_id, start_date="1900-01-01", end_date="2025-12-01"):
    """
    Fetches and normalizes data from Statistics Canada vectors.

    Parameters:
        ds (DataSource): The DataSource object for Statistics Canada vectors.
        vector_id (str): The ID of the vector to fetch.
        start_date (str, optional): The start date for the data request. Defaults to "1900-01-01".
        end_date (str, optional): The end date for the data request. Defaults to "2025-12-01".
    
    Returns:
        pd.Series: A pandas Series containing the normalized vector data.
    """
    # Set the paramters for the API request
    params = {"vector_id": vector_id, "start_date": start_date, "end_date": end_date}
    
    # Get the API request urls
    data_url = ds.dataUrl(params)
    metadata_url = ds.metadataUrl(params)

    # Perform the API request and get the data 
    rawData = ds.get(data_url)
    ds.checkRequest(rawData)

    # Perform the API request and get the metadata 
    metadata = ds.post(metadata_url["api_metadata_url"], metadata_url["body"])

    # Normalize the API request responses and save the resulting Series
    series = ds.normalize(rawData, metadata)
    ds.saveData(series)
    return series

def summarizeSeries(series):
    """
    Summarizes a pandas Series by printing its name, index name, and size.
    Also prints the first 10 entries.

    Parameters:
        series (pd.Series): The pandas Series to summarize.
    """
    print("Series name:"+series.name)
    print("Series index name:"+series.index.name)
    print("Series size:"+str(series.size))
    # Print the first 10 entries so that they are visible in the terminal
    with pd.option_context(
        "display.max_columns", None,
        "display.width", None,
        "display.max_colwidth", None,
    ):
        print(series.head(5))
scVectors = DataSource("Stats Canada Vectors", 
    dataUrl=dataUrlStatsCanVectors, 
    metadataUrl=metadataUrlStatsCanVectors, 
    normalize=normalizeRequestStasCanVectors, 
    checkRequest=checkRequestStatsCan, 
    dtype=pd.Series,)

def dataUrlStatsCanTable(parameters):
    """
    Creates the API request URL for fetching data from Statistics Canada tables.

    Parameters:
        parameters (dict): A dictionary containing the API request parameters.

    Returns:
        str: The API request URL.
    """
    # Get API request paramters from the dictionary and store them in variables
    product_id = parameters["product_id"] if parameters["product_id"] is str else str(parameters["product_id"])
    if "," in product_id:
        raise ValueError("Cannot request more than vector at a time.")
    pass
    product_id = product_id.replace("-", "")[:8] # Slice the correct section of the string

    # Create the API request URL for the data
    api_url = ("https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/"
    f"{product_id}/en")

    return api_url

def metadataUrlStatsCanTable(parameters):
    """
    Creates the API request URL for fetching metadata from Statistics Canada tables.

    Parameters:
        parameters (dict): A dictionary containing the API request parameters.

    Returns:
        dict: A dictionary containing the API request URL and the request body.
    """
    # Get API request paramters from the dictionary and store them in variables
    product_id = parameters["product_id"] if parameters["product_id"] is str else str(parameters["product_id"])
    if "," in product_id:
        raise ValueError("Cannot request more than vector at a time.")
    pass
    product_id = product_id.replace("-", "")[:8] # Slice the correct section of the string

    # Create API request URL for metadata
    api_metadata_url = "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata"
    body = [{"productId":product_id}]
    return {"api_metadata_url":api_metadata_url, "body":body}

def normalizeRequestStatsCanTable(dataResponse, metadataResponse):
    """
    Normalizes the API response for Statistics Canada tables.

    Parameters:
        dataResponse (bytes): The raw API response for the data.
        metadataResponse (list): The API response for the metadata.

    Returns:
        pd.Series: A pandas Series containing the normalized vector data.
    """
    # Create a temp file to save the zip file in the API response
    temp_path = Path(__file__).resolve().parent / "temp"

    # Convert the bytes contant back into a Response object
    response = requests.Response()
    response.raw = io.BytesIO(dataResponse)
    response.status_code = 200
    response.headers = {'Content-Type': 'application/zip'}

    # Write the Zip file into memory by chunk 
    with open(temp_path, "wb") as file:
        for chunk in response.iter_content(chunk_size=1024 * 1024): # Iterate through the chunks of the response;
            if chunk: # If the chunk isnt empty, write them into the file just opened
                file.write(chunk) 
    
    # Read the .csv out of the zip file
    with ZipFile(temp_path) as zipped_table: #open the downloaded zip file
    # A list comprehension that produces the list of .csv filenames in the zip file
        csv_files = [
            name for name in zipped_table.namelist() #iterate through all of the filenames in the zipped file, zipped_table.namelist() returns a list of filenames in the zipped file
            #the first name is the names kept
            if name.endswith(".csv") and "MetaData" not in name #this condition means that only .csv files are kept and the string "MetaData" is not in the name of the csv file
            ]
        with zipped_table.open(csv_files[0]) as file: #this opens the first .csv file found in the zip file
            table = pd.read_csv(file, low_memory=False) #this reades the .csv file into a pandas data frame
    

    # Get the vector frequency info from the data 
    frequencyCode = metadataResponse[0]["object"]["frequencyCode"]
    frequency = convertFrequencyCode(frequencyCode)[0]
    frequencyPeriod = convertFrequencyCode(frequencyCode)[1]
    frequencyUnit = convertFrequencyCode(frequencyCode)[2]

    # Get the vector title and frequency inro from the metadata 
    title = metadataResponse[0]["object"]["cubeTitleEn"]
    title = title + f" ({frequency})" 

    # Write the name into a new global attribute of the table called name.
    table.attrs["name"] = title

    # Handle value scaling
    table["VALUE"] = table["VALUE"].apply(lambda value: Decimal(str(value)))
    table["VALUE"] = table["VALUE"].mul(10 ** (table["SCALAR_ID"]))

    # Drop unnecessary columns
    table.drop(columns=["TERMINATED", "SYMBOL", "STATUS", "VECTOR", "COORDINATE", "DECIMALS","UOM_ID", "SCALAR_ID", "SCALAR_FACTOR"], inplace=True)
        # TERMINATED:
        # SYMBOL: 
        # STATUS: 
        # VECTOR:
        # COORDINATE:
        # DECIMALS:
        # UOM_ID:
        # SCALAR_ID:
        # SCALAR_FACTOR:

    # Delete the temp file we created at the beginning of the function
    temp_path.unlink(missing_ok=True)

    return table 

def runStatsCanTables(ds, product_id):
    """
    Runs the Statistics Canada tables data fetching and normalization process.

    Parameters:
        ds (DataSource): The data source object.
        product_id (str): The product ID for the API request.

    Returns:
        pd.DataFrame: The normalized DataFrame containing the requested data.
    """
    # Set the paramters for the API request
    params = {"product_id": product_id}

    #Get the API request urls
    data_url = ds.dataUrl(params)
    metadata_url = ds.metadataUrl(params)

    # Perform the API request and get the data 
    zipData = ds.get(data_url)
    zip_url = zipData["object"]
    print("Getting the data file...")
    rawData = ds.get(zip_url, stream=True)

    # Perform the API request and get the metadata 
    metadata = ds.post(metadata_url["api_metadata_url"], metadata_url["body"])

    # Normalize the API request responses and save the resulting DataFrame
    print("Normalizing the data...")
    table = ds.normalize(rawData, metadata)
    print("Saving the data...")
    ds.saveData(table)
    return table

def summarizeTable(table):
    """
    Summarizes a pandas DataFrame by printing its name, index name, and size.
    Also prints the first 5 entries.

    Parameters:
        table (pd.DataFrame): The pandas DataFrame to summarize.
    """
    print("Table name: " +table.attrs["name"])
    print("Table index name: "+str(table.index.name))
    print("Table size: "+str(table.size))
    with pd.option_context(
        "display.max_columns", None,
        "display.width", None,
        "display.max_colwidth", None,
    ):
        print(table.head(5))
scTables = DataSource("Stats Canada Tables",
    dataUrl=dataUrlStatsCanTable,
    metadataUrl=metadataUrlStatsCanTable,
    normalize=normalizeRequestStatsCanTable,
    checkRequest=checkRequestStatsCan
)

if __name__ == "__main__":
    table = runStatsCanTables(scTables,"36-10-0434-02")
    summarizeTable(table)
    scTables.printSavedData()
