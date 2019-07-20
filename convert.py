#!/usr/bin/env python3

import sys
import re
import os
import argparse
import xml.etree.ElementTree as ET
import csv


class Handler:
    _reqkeys = ['title','addon_id','version_id','version_string']
    _titlerow = ["Title", "To Translate", "Translation"]

    def __init__(self, args):
        self._ifile = args.input_file # input file (path)
        self._ofile = args.output_file # output file (name)
        self._efile = args.extra_file # exta file (path) for XML to CSV
        self._reverse = args.reverse # whether to do the reverse conversion operation of CSV to XML
        self._reffile = args.reference_file # reference file for CSV to XML
        self._nolog = args.no_log # whether or not to generate a log for CSV to XML

        self._default_oname = False #will be true if we used a default output name
        self._used_efile = False # will be true if we used an extra file


    def handle(self):
        self._validate()

        if not self._reverse:
            #XML -> CSV
            self._xmlcsv()
        else:
            #CSV -> XML
            self._csvxml()
        
        self._printresults()


    def _printresults(self):
        if not self._reverse:
            print(f'''===============================================
                    \nProcess complete. Conversion XML to CSV
                    \n{self._ifile} => {self._newfile_fullpath}
                    \nUsed default output name: {self._yn(self._default_oname)}
                    \nUsed extra file: {self._yn(self._used_efile)}
                    \n===============================================''')
        else:
            log = ""
            if not self._nolog:
                p = self._get_logpath(False)
                log = f"\nSee log file for more details: {p}"

            print(f'''===============================================
                    \nProcess complete. Conversion CSV to XML
                    \n{self._ifile} + {self._reffile} => {self._newfile_fullpath}
                    \nUsed default output name: {self._yn(self._default_oname)}
                    \nRequested log: {self._yn(not self._nolog)} {log}
                    \n===============================================''')


    # Contains both versions of XML to CSV
    def _xmlcsv(self):
        #both xml to csv conversions
        if not self._used_efile:
            self._xml_to_csv()
        else:
            self._xml_to_csv_duos()


    # XML to CSV
    def _xml_to_csv(self):
        self._alert_processing()

        tree = ET.parse(self._ifile)

        with open(self._newfile_fullpath, "w+", newline='', encoding='utf-8') as csvFile:

            writer = csv.writer(csvFile)
            writer.writerow(Handler._titlerow) #1st row/header
            i = 0
            print("")

            for elem in tree.iter():
                i += 1
                self._processing_counter(i)

                if not self._xml_elm_isvalid(elem):
                    continue

                #we've validated it was a correct element
                #now gonna write to CSV file
                writer.writerow([elem.get('title', default=''), elem.text, ''])
            
            self._processing_end_counter(i)
            print("")

        csvFile.close()

    # XML to CSV with some translations
    def _xml_to_csv_duos(self):
        self._alert_processing()

        tree = ET.parse(self._ifile)

        #We can now loop through the original XML and create a dict we will be able to use
        #To keep track of translations in the 2nd XML file...
        
        elms1 = 0
        allitems = {}

        print("\nProcessing Input XML...")

        for elem in tree.iter():
            elms1 += 1
            self._processing_counter(elms1)

            if not self._xml_elm_isvalid(elem):
                continue
            
            allitems[elem.get('title')] = { "orig" : elem.text, "trans" : ""}
        self._processing_end_counter(elms1)

        #Now we will iterate over the 2nd one and fill up our dictionary
        tree = ET.parse(self._efile)
        elms2 = 0

        print("\nProcessing Supplemental XML...")

        for elem in tree.iter():
            elms2 += 1
            self._processing_counter(elms2)

            if not self._xml_elm_isvalid(elem):
                continue

            # Now we fill out the secondary item if it exists
            title = elem.get('title')
            if allitems.get(title) is not None:
                allitems[title]["trans"] = elem.text
        self._processing_end_counter(elms2)


        #Now that we have a list of items along with their possible translations, we can create our CSV

        with open(self._newfile_fullpath, "w+", newline='', encoding='utf-8') as csvFile:
            
            writer = csv.writer(csvFile)
            writer.writerow(Handler._titlerow) #1st row/header

            print("\nNow writing finalized list...")

            i = 0
            #Finally write all the data
            for key, value in allitems.items():
                i += 1
                self._processing_counter(i)
                writer.writerow([key, value["orig"], value["trans"]])
            
            self._processing_end_counter(i)
            print("")

        csvFile.close()


    # CSV to XML
    def _csvxml(self):
        #csv to xml conversion
        self._alert_processing()
        
        newdata = {} #dictionary for new data to be added to new XML file 
        newdata_title = {} #main container data
        log = {
            "info" : {
                "input_csv" : self._ifile,
                "input_xml" : self._reffile,
                "default_name" : self._yn(self._default_oname)
            },
            "log" : {
                "error_notfound" : { #for data that existed in CSV (based off of title/id) but not in reference XML
                    "title" : "Not Found",
                    "count": 0,
                    "desc" :  '''This is data that existed in the provided CSV file but its 
                    \nID was not found in the reference XML file. This data was thus lost''',
                    "list" : {
                        #fill this out
                    }
                },
                "error_empty" : { #CSV data that had an empty translation field
                    "title" : "Empty Translation",
                    "count": 0,
                    "desc" :  '''This is data that existed in the CSV file but had an empty translation field''',
                    "list" : {
                        #fill this out
                    }
                },
                "notice_empty" : { #for data that existed in initial XML parse but was never given a translation
                    "title" : "No Translation",
                    "count": 0,
                    "desc" :  '''This is data that existed in the XML reference but was not given a translation, thus discarded.''',
                    "list" : {
                        #fill this out
                    }
                }
            }
        }

        tree = ET.parse(self._reffile)
        
        print("\nProcessing Reference XML...")
        
        newdata_title = {
            "title" : tree.getroot().tag,
            "data" : self._csvxml_gettitle(tree, self._ofile)
        }

        i = 0
        for elem in tree.iter():
            
            if elem.tag != 'phrase': continue #skip anything that isn't a phrase tag, which would be the container tag

            i += 1
            self._processing_counter(i)

            newdata[elem.get('title')] = {
                "addon_id" : elem.get('addon_id'),
                "version_id" : elem.get('version_id'),
                "version_string" : elem.get('version_string'),
                "orig" : elem.text,
                "contents" : None
            }
        self._processing_end_counter(i)


        # Now we parse the CSV...
        print("\nProcessing input CSV...")
        i = 0
        with open(self._ifile, "r", newline='', encoding='utf-8') as csvfile:

            reader = csv.reader(csvfile)

            for row in reader:
                i += 1
                if i == 1: #skip title row
                    continue
                self._processing_counter(i)

                if row[0] in newdata:
                    #key exists in reference XML data
                    if self._csv_itemnotempty(row[2]):
                        #Translation was filled out
                        newdata[row[0]]['contents'] = row[2]
                    else:
                        #There was no translation
                        log["log"]["error_empty"]["count"] += 1
                        log["log"]["error_empty"]["list"][row[0]] = self._csvxml_geterroritem(row)
                else:
                    #Key did not exist in reference XML
                    log["log"]["error_notfound"]["count"] += 1
                    log["log"]["error_notfound"]["list"][row[0]] = self._csvxml_geterroritem(row)

            self._processing_end_counter(i)

        csvfile.close()


        #Now we start writing our new XML file...
        print("\nGenerating Output File...")
        container = ET.Element(newdata_title["title"], newdata_title["data"])
        i = 0

        for key, value in newdata.items():
            i += 1
            self._processing_counter(i)

            if value['contents'] is not None:
                #The value of contents was set in our earlier loop, so we can append it to the ElementTree
                d = {'title' : key}

                for k, item in value.items():
                    if k != 'contents' and k != 'orig':
                        d[k] = item

                data = value['contents']
                cont = ET.SubElement(container, 'phrase', d)
                cont.append(ET.Comment(' --><![CDATA[' + data.replace(']]>', ']]]]><![CDATA[>') + ']]><!-- '))

                #ET.SubElement(container, 'phrase', d).text = value['contents']
            else:
                # the value of contents was empty. add it to our error log output...

                log["log"]["notice_empty"]["count"] += 1
                log["log"]["notice_empty"]["list"][key] = self._csvxml_geterroritem_dict(value)
        
        self._processing_end_counter(i)

        # Now create and write to file
        print("\nWriting to output File...")

        newtree = ET.ElementTree(container)
        open(self._newfile_fullpath, "w+", newline='', encoding='utf-8').close() #just create file
        newtree.write(self._newfile_fullpath, xml_declaration=True, encoding='utf-8')

        print("\nDone!")
        
        if not self._nolog:
            # Now we can write a simple output log file
            print("\nWriting Log File...")
            
            logf = self._get_logpath()
            if logf is not None:
                #Log file path could be generated and was valid, so let's write the file
                f = open(logf, "w+", newline='', encoding='utf-8')
                
                e1 = log['log']['error_notfound']
                e2 = log['log']['error_empty']
                e3 = log['log']['notice_empty']

                f.write(f'''========= [ Process Log for CSV to XML conversion ] =========
                \nInput CSV: {log['info']['input_csv']}
                \nInput XML: {log['info']['input_xml']}
                \nOutput Name: {self._newfile_fullpath}
                \nUsed Default Output Name: {log['info']['default_name']}
                \r\n======================== [ Errors ] ========================
                \nTotal Errors: {e1['count'] + e2['count']}
                \nTotal Notices: {e3['count']}\n''')
                
                #In case there was anything notable
                if 0 < (e1['count'] + e2['count'] + e3['count']):
                    f.write("==================== [ Error Details: ] ====================\r\n")
                    
                    self._write_err(f,e1)
                    self._write_err(f,e2)
                    self._write_err(f,e3)

                f.close()
                print("\nDone!")
            else:
                print("\nLog file could not be created.")



    def _write_err(self, f, error):
        if error['count'] > 0:
            f.write(f'''{error['count']} errors of type {error['title']}
                \n{error['desc']}
                \n-------------------------------------------------------------------\n''')

            for k, v in error['list'].items():
                f.write(f'"{k}" : {v}\r\n')
            f.write("\r\n-------------------------------------------------------------------\r\n")

    def _csvxml_gettitle(self, tree, title):
        e = tree.getroot()
        #<language title="English (US)" date_format="M j, Y" time_format="g:i A" decimal_point="." thousands_separator="," language_code="en-US" text_direction="LTR">
        r = {
            "title" : title,
            "date_format" : e.get("date_format"),
            "time_format" : e.get("time_format"),
            "decimal_point" : e.get("decimal_point"),
            "thousands_separator" : e.get("thousands_separator"),
            "language_code" : e.get("language_code"),
            "text_direction" : e.get("text_direction"),
        }
        return r

    def _csv_itemnotempty(self, string):
        return string != ''

    def _csvxml_geterroritem_dict(self, d):
        r = {
            "orig" : d['orig'],
            "trans" : None
        }
        return r

    def _csvxml_geterroritem(self, row):
        transl = row[2] if row[2] != '' else None

        d = {   "orig" : row[1],
                "trans" : transl }
        return d

    def _xml_elm_isvalid(self, element):
        if element.tag != 'phrase':
            return False
            # element is not of the valid type

        if not self._hasrequiredkeys(element.attrib):
            return False
        
        return True

    def _yn(self, b):
        return "Yes" if b else "No"      

    def _processing_counter(self, i):
        sys.stdout.write('\r')
        sys.stdout.write(f"Processing line {i}...")
        sys.stdout.flush()

    def _processing_end_counter(self, i):
        sys.stdout.write('\r')
        sys.stdout.write(f"Done! Processed {i} items total.\n")
        sys.stdout.flush()

    def _alert_processing(self):
        if not self._reverse:
            #Alert for XML -> CSV process
            print("Processing XML to CSV conversion...")
        else:
            #Alert for CSV -> XML conversion
            print("Processing CSV to XML conversion...")



    def _validate(self):
        if not self._valid_ifiles():
            exit()

        if not self._valid_fname(self._gen_get_oname()):
            exit()

        self._newfile_fullpath = self._get_opath() 

    def _gen_get_oname(self):
        '''gets and handles correct output file name'''

        if not self._ofile:
            base = os.path.basename(self._ifile)
            self._ofile = os.path.splitext(base)[0] + "_output"
            self._default_oname = True
            # if no output file was provided then we use a default output file name

        # else self._ofile is staying what it is
        return self._ofile

    def _get_opath(self):
        outpath = os.path.dirname(os.path.abspath(self._ifile))

        if not self._reverse:
            # XML -> CSV
            newfile = outpath + '\\' + self._ofile + ".csv"

            if os.path.isfile(newfile):
                print(f"File of the name {self._ofile}.csv already exists at {outpath}")
                exit()

            return newfile

        else:
            # CSV -> XML
            newfile = outpath + '\\' + self._ofile + ".xml"
            
            if os.path.isfile(newfile):
                print(f"File of the name {self._ofile}.xml already exists at {outpath}")
                exit()

            return newfile

    def _get_logpath(self, check_path=True):
        # CSV to XML only
        outpath = os.path.dirname(os.path.abspath(self._ifile))
        newfile = outpath + '\\' + self._ofile + "_log.txt"
        
        if check_path:
            if os.path.isfile(newfile):
                print(f"Failure generating log file: file of the name {self._ofile}_log.txt already exists at {outpath}")
                return None
        
        return newfile

    def _valid_fname(self, string):
        '''valid windows file name'''
        pattern = re.compile('^(?!\s{1,255})(((?![<>:"/\\|?*\.]).){1,254}(?![\.\s]).?)$')
        return pattern.search(string)

    def _hasreqkeys(self, d):
        '''return true if supplied dict has all required keys (_reqkeys)'''

        for key in _reqkeys:
            if key not in d:
                return False
        return True

    def _valid_ifiles(self):
        '''true if file is valid'''
        if not self._reverse:
            #Regular operation of XML -> CSV

            if not os.path.isfile(self._ifile):
                print("Input file is not a valid file")
                return False

            if not self._ifile.lower().endswith('.xml'):
                print("Input file is not xml")
                return False

            if self._efile:
                #if extra file was provided
                if not os.path.isfile(self._efile):
                    print("Extra file is not a valid file")
                    return False

                if not self._ifile.lower().endswith('.xml'):
                    print("Extra file is not xml")
                    return False
                self._used_efile = True

            return True
        else:
            #Opposite operation of CSV -> XML

            if not os.path.isfile(self._ifile):
                print("Input file is not a valid file")
                return False

            if not self._ifile.lower().endswith('.csv'):
                print("Input file is not csv")
                return False

            if not self._reffile:
                print("Reference file not provided. This is required. Use -r to provide Reference XML file.")
                return False

            if not os.path.isfile(self._reffile):
                print("Reference file is not a valid file")
                return False
            
            if not self._reffile.lower().endswith('.xml'):
                print("Reference file is not xml")
                return False

            return True

    def _hasrequiredkeys(self, d):
        for key in self._reqkeys:
            if key not in d:
                return False
        return True



def main():
    parser = argparse.ArgumentParser(description='Parses Xenforo Phrase XML into CSV alone or with a supplementory translation XML, can also parse CSV back to Xenforo XML.')

    parser.add_argument('-i','--input-file',help='Main input XML file to parse into CSV, or CSV file to parse into XML if using -R flag.', required=True)
    parser.add_argument('-o','--output-file',
        help='''Output file name of the CSV/XML file to be created. It will go in the same directory as the input file. 
        If not provided, will default to input file name followed by "_output".''',
        default=False)
    parser.add_argument('-e','--extra-file', 
        help='''[ XML -> CSV ] Additional XML file to include that already contains some translations. 
        This is OPTIONAL, and only for a XML to CSV conversion. If this is not provided it 
        simply won't be used to fill out the third field of translations.''', 
        default=False)
    parser.add_argument('-r','--reference-file', 
        help='''[ CSV -> XML] XML file that contains the most updated Xenforo XML format to reference during parsing of a 
        CSV file back into XML for usage in xenforo. REQUIRED for a 
        CSV to XML conversion operation.''', 
        default=False)
    parser.add_argument('-R','--reverse',help='''[ CSV -> XML ] This is a flag that is used for a backwards conversion from CSV into XML''', action='store_true')
    parser.add_argument('-NL','--no-log',help='''[ CSV -> XML ] This is a flag to skip generation of a log for CSV to XML conversions''', action='store_true')
    
    parsed_args = parser.parse_args()

    #Handling:
    hdlr = Handler(parsed_args)
    hdlr.handle()


    
if __name__ == "__main__":
    main()