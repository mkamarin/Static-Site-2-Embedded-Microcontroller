#!/usr/bin/python3

""" Convert a static web site to and enbedded system

This script can be used to encode an static web site (for example one generated
by Hugo (https://gohugo.io/) to an embedded site to be hosted in a microcontroller
"""

import os
import re
import io
import sys
import getopt
import inspect
import datetime
import mimetypes

verbose = False

def vbprint(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)

def error(*args, **kwargs):
    print("ERROR (:",os.path.basename(sys.argv[0]),":",inspect.currentframe().f_back.f_lineno,")",
            *args, **kwargs, sep="", file = sys.stderr)

# This is internal template that guides the generation of the sample code
template = '''
/****************************************
 * Program arguments:
 * Path='[:::Path:::]'
 * Output='[:::Output:::]'
 * Use='[:::Use:::]'
 * Write='[:::Write:::]'
 * Include='[:::Include:::]'
 * If='[:::If:::]'
 * Type='[:::Type:::]'
 * Compress='[:::Compress:::]'
 **************************************** 
 * START Configuration Section
 ****************************************/

// Define USE_ASYNC if you want to use ESPAsyncWebServer.h instead of WebServer.h
//#define USE_ASYNC

// These are the WiFi credential for your router
const char* ssid = "";
const char* password = "";

/****************************************
 * END Configuration Section
 ****************************************/

#include <WiFi.h>
#ifdef USE_ASYNC
#include <ESPAsyncWebServer.h> // From: https://github.com/me-no-dev/ESPAsyncWebServer
#else
#include <WebServer.h>
#endif

struct htmlSections
{
    int start, length;
    char fname[];
};

:::include

#ifdef USE_ASYNC
AsyncWebServer server(80);
#else
WebServer server(80);
#endif

int cnt(0);

#ifdef USE_ASYNC

:::for files  
void get[:::Name:::](AsyncWebServerRequest *request)
{
    request->send_P(200, "[:::MIME:::]", [:::Page:::]);
}
:::end

#else // Non-Async

:::for files  
void get[:::Name:::](void)
{
    server.sendHeader("Connection", "close");
    server.send_P(200, "[:::MIME:::]", [:::Page:::]);
}
:::end

#endif

void setup() 
{
  Serial.begin(115200);

  Serial.printf("\\n=======\\n\\nSTART connecting to %s\\n", ssid);
  WiFi.begin(ssid, password);
 
  Serial.println("Connecting to WiFi.");
  while (WiFi.status() != WL_CONNECTED) 
  {
    delay(500);
    Serial.print(".");
  } 

  String IP = WiFi.localIP().toString();
  Serial.printf("Connected to: %s\\n IP address: %s\\n Host name:  %s\\n",
      ssid, IP.c_str(), WiFi.getHostname());

:::for 
:::if NOT P404Html
  server.on("[:::HtmlPath:::]", HTTP_GET, &get[:::Name:::]); 
:::fi
:::# This due to lack of else block
:::if P404Html
  server.onNotFound(&get[:::Name:::]); 
:::fi
:::end
  server.begin();
}

void loop()
{
#ifndef USE_ASYNC
  server.handleClient();
  yield(1);
#endif
}
'''

def clean_name(name):
    """Clean a directory or folder name by removing special characters

    Parameters
    ----------
    name: str
        file name

    Returns
    -------
    str
    """

    k = name.rfind(os.sep)
    if k < 0:
        pth = ""
        nm = name
    else:
        nm = name[k+1:]
        pth = name[:k] + os.sep

    k = nm.rfind(".")
    if k < 0:
        ext = ""
        rest = re.sub(r'[^0-9a-zA-Z-]+', '-', nm)
    else:
        ext = "." + nm[k+1:]
        rest = re.sub(r'[^0-9a-zA-Z-]+', '-', nm[:k])

    if rest.endswith('-'):
        rest = rest[:-1]

    return pth + rest + ext 


def clean_dir(folder):
    """Clean a directory or folder name by removing special characters

    Parameters
    ----------
    folder: str
        directory or folder name

    Returns
    -------
    str
    """

    out = folder.split(os.sep)
    while('' in out):
        out.remove('')
    ret = []    
    for e in out:
        ret.append(re.sub(r'[^0-9a-zA-Z-]+', '-', e))

    rtrn = ""
    if folder and folder[0] == os.sep:
        rtrn = os.sep + os.sep.join(ret)
    elif folder:
        rtrn = os.sep.join(ret)

    return rtrn


def do_cmd(cmd, frame, argDict):
    """Process a command from a frame

    Parameters
    ----------
    cmd: str
        Command to be processed
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information

    Returns
    -------
    str
    """

    if not frame:
        error("Invalid frame")
        return "???"

    if cmd == ":MIME:":
        return frame['mime']
    elif cmd == ":Name:":
        return frame['vname']
    elif cmd == ":Page:":
        if argDict['arType'] in ['s', 'm']:
            return frame['vname']
        elif argDict['arType'] == 'f':
            return frame['ffname']
        elif argDict['arType'] == 'c':
            return frame['cname']
    elif cmd == ":HtmlPath:":
            return frame['html']

    return cmd

def nextline(flTemplate):
    """Reads the next line of the template

    Parameters
    ----------
    flTemplate: an io stream (either string or from a file)
        Contain the current position on the io stream that we are reading

    Returns
    -------
    Next line of the template
    """
    line = flTemplate.readline()
    vbprint("[[[[%s]]]]",line[:-1])
    return line

def genline(line, frame, argDict):
    """Process each output line of the template to replace variables

    Parameters
    ----------
    line: str
        line in the template to be written to the generated file
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information

    Returns
    -------
    str
    """

    if ("[:::" in line) and (":::]" in line):
        vbprint("FRAME:",frame)
        tokens = re.split(r"(?:\[::)|(?:::\])",line)
        vbprint("TOKENS",len(tokens),tokens)
        newline = ""
        for token in tokens:
            if token in [":HtmlPath:", ":Name:", ":MIME:", ":Page:"]:
                newline += do_cmd(token, frame, argDict)
            elif token == ":Path:":
                newline += argDict['arPath']
            elif token == ":Output:":
                newline += argDict['arOutput']
            elif token == ":Use:":
                newline += argDict['arUse']
            elif token == ":Write:":
                newline += argDict['arWrite']
            elif token == ":Include:":
                newline += argDict['arInclude']
            elif token == ":If:":
                newline += ','.join(argDict['arIf'])
            elif token == ":Compress:":
                newline += "True" if argDict['arCompress'] else "False"
            elif token == ":Type:":
                newline += argDict['arType']
            elif (token == "") or (token == None):
                newline += ""
            else:
                newline += token
        return newline
    else:
        return line




def execfor(line, flTemplate, flOutput, argDict):
    """Process template file until it reaches the end token

    Parameters
    ----------
    line: str
        line in the template that contains the command to be executed
    flTemplate: an io stream (either string or from a file)
        Contain the current position on the io stream that we are reading
    flOutput  : output file
        The output file to write to
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)

    Returns
    -------
    Nothing
    """

    vbprint("FOR BLOCK")
    start = flTemplate.tell()
    for e in argDict['lst']:
        while True:
            line = nextline(flTemplate)
            if not line:
                error("Template EOF within an :::for block")
                return

            if line.startswith(":::end"):
                end = flTemplate.tell()
                flTemplate.seek(start)
                break
            elif line.startswith(":::"):
                execute(line, flTemplate, flOutput, argDict, e)
            else:
                flOutput.write(genline(line, e, argDict))
    flTemplate.seek(end)
    vbprint("END FOR BLOCK")



def execif(line, flTemplate, flOutput, argDict,frame):
    """Process template file until it reaches the end token

    Parameters
    ----------
    line: str
        line in the template that contains the command to be executed
    flTemplate: an io stream (either string or from a file)
        Contain the current position on the io stream that we are reading
    flOutput  : output file
        The output file to write to
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)

    Returns
    -------
    Nothing
    """

    vbprint("IF BLOCK (include)")
    while True:
        line = nextline(flTemplate)
        if not line:
            error("Template EOF within an :::if block")
            break

        if line.startswith(":::fi"):
            vbprint("END IF BLOCK (include)")
            return
        if line.startswith(":::"):
            execute(line, flTemplate, flOutput, argDict, frame)
        else:
            flOutput.write(genline(line, frame, argDict))



def skipif(line, flTemplate, flOutput, argDict, frame):
    """skip template file until it reaches the end token

    Parameters
    ----------
    line: str
        line in the template that contains the command to be executed
    flTemplate: an io stream (either string or from a file)
        Contain the current position on the io stream that we are reading
    flOutput  : output file
        The output file to write to
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)

    Returns
    -------
    Nothing
    """

    vbprint("IF BLOCK (skip)")
    while True:
        line = nextline(flTemplate)
        if not line:
            error("Template EOF within an :::if block")
            break

        if line.startswith(":::if"):
            skipif(line, flTemplate, flOutput, argDict, frame)
        elif line.startswith(":::fi"):
            vbprint("END IF BLOCK (skip)")
            return



def evalif(tokens , vars):
    """evaluates an if condition (boolean expression) using eval()

    Parameters
    ----------
    tokens: list
        List of tokens in the condition
    vars : List
        List of defined variables (either by --if argument or internal)

    Returns
    -------
    True or False
    """

    if not tokens:
        return False

    # This is inefficient but we should not have many complicated :::if statements
    tmp = ' '.join(tokens).replace('(', ' ( ').replace(')', ' ) ')
    tokens = tmp.rstrip().split(' ')
    while('' in tokens):
        tokens.remove('')

    exp = ""
    for tkn in tokens:
        if (tkn in ['NOT', 'AND', 'OR']) or (tkn in ['(',')']):
            exp += tkn.lower() + ' '
        elif tkn in vars:
            exp += "True "
        else:
            exp += "False "

    try:
        ret = eval(exp)
    except:
        error("Invalid :::if ",tokens,"=>",exp)
        ret = False

    return ret


def execute(line, flTemplate, flOutput, argDict, frame):
    """Executes a command in the template file (line starting with :::

    Parameters
    ----------
    line: str
        line in the template that contains the command to be executed
    flTemplate: an io stream (either string or from a file)
        Contain the current position on the io stream that we are reading
    flOutput  : output file
        The output file to write to
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information
    frame: dictionary
        Dictionary with the current FOR frame in the stack (for vars)

    Returns
    -------
    Nothing
    """

    tokens = line.rstrip().split(' ')
    while('' in tokens):
        tokens.remove('')

    vbprint("CMD line tokens:", tokens,"=",len(tokens))
    if tokens[0] == ":::include":
        vbprint("Processing INCLUDE for",argDict['arType'])
        if argDict['arType'] == "m": # Each file got its own header file 
            for e in argDict['lst']:
                flOutput.write('#include "' + e['finame'] + '"\n')
        elif argDict['arType'] == "s": # Single header
            flOutput.write('#include "' + argDict['arInclude'] + '"\n')
        else:
            flOutput.write('#include "html-list.h"\n')
    elif tokens[0] == ":::if":
        vares = argDict['arIf'].copy()
        if frame:
            vares.append(frame['vname'])
            if frame['mime'] == 'text/html':
                vares.append('HTML')
        vbprint("Processing ", line[:-1], " => ",tokens, "\nTrue values: ",vares,sep="")
        if evalif(tokens[1:],vares):
            execif(line, flTemplate, flOutput, argDict, frame)
        else:
            skipif(line, flTemplate, flOutput, argDict, frame)
    elif tokens[0] == ":::for":
        vbprint("Processing ",line[:-1])
        execfor(line, flTemplate, flOutput, argDict)
    elif tokens[0] == ":::#":
        vbprint("Ignoring   ",line[:-1])


def add_header(fl, fn):
    """Add the header at the begining of the file

    Parameters
    ----------
    fl : File
         Text file to write the header
    fn : str
         Name of the file

    Returns
    -------
    Nothing
    """

    fl.write("//\n// File: " + fn + "\n// Sample code generated by " + 
            os.path.basename(sys.argv[0]) + "\n//\n")


def generate_index(fl, var, sz, lindex):

    fl.write("\n#define " + var + "_LENGTH  " + str(sz) + "\n")

    if not lindex:
        fl.write("struct htmlSections " + var + "_Blocks[] = NULL;\n")
        return

    fl.write("struct htmlSections " + var + "_Blocks[] =\n{")
    for e in lindex:
        fl.write('{' + str(e['start']) + ', ' + str(e['length']) + ', "' + e['mark'] + '"},\n')
    fl.write("{0, 0, NULL}};\n")



def generate(argDict,extraIf):
    """Generate an example file for Arduino IDE

    Parameters
    ----------
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information

    Returns
    -------
    Nothing
    """

    try:
        fnName = os.path.join(argDict['arOutput'], os.path.basename(argDict['arOutput']) + ".ino")
        vbprint("\nGENERATION phase (into '", fnName,"')",sep="")
        print("Full set of defined variables: ", ', '.join(argDict['arIf']), "\n",", ".join(extraIf),
                "\n",sep="")
        if not argDict['arUse']:
            flTemplate = io.StringIO(template)
        else:
            try:
                flTemplate = open(argDict['arUse'], 'rt')
            except OSError as e:
                error(e, " unable to open",argDict['arUse'])


        if argDict['arType'] in ['f','c']:
            try:
                fnlst = os.path.join(argDict['arOutput'], "html-list.h")
                fllst = open(fnlst, 'wt')
                fllst.write("#ifndef HTML_LIST_H\n#define HTML_LIST_H\n")
                add_header(fllst, "html-list.h")
                for e in argDict['lst']:
                    if e['mime'] == 'text/html':
                        generate_index(fllst, e['vname'], e['size'], e['index'])

                fllst.write("\n#endif\n")
                fllst.close()
            except OSError as e:
                error(e, " unable to generate",fnlst)

        flOutput = open(fnName, 'wt')
        add_header(flOutput, fnName)

        # Process template
        while True:
            line = nextline(flTemplate)
            if not line:
                break

            if line.startswith(":::"):
                execute(line, flTemplate, flOutput, argDict, {})
            else:
                flOutput.write(genline(line, {}, argDict))

        flOutput.close()

    except OSError as e:
        error(e, " while generating ",fnName)


def writetemplate(arWrite):
    """Write the internal template to arWrite

    Parameters
    ----------
    arWrite  : str (file name)
        File name to write internal template to

    Returns
    -------
    Nothing
    """

    try:
        flWrite = open(arWrite, 'w')
        flWrite.write(template)
        flWrite.close()

    except OSError as e:
        error(e, " while writing out the internal template")


def process_html(flIn, flOut, arCompress):
    """Process an html file line by line copying it to the output

    Parameters
    ----------
    flIn : file
        Input file
    flOut : file
        Output file
    arCompress : boolean
        Compress argument

    Returns
    -------
    sz : int
        size (length) of the output
    lindex : list
        List of markers in the input file and their position in the output file
    """


    sz = 0
    start = 0
    lindex = []
    while True:
        line = flIn.readline()
        if not line:
            break

        if arCompress:
            line = line.lstrip()
            if not line:
                continue

        marker1 = line.find('(:::')
        while marker1 >= 0:
            marker2 = line.find(':::)',marker1 + 4)
            if marker2 < 0:
                error("wrong marker")
            else:
                lng = sz + marker1 - start
                mark = line[marker1 + 4: marker2]
                lindex.append({'start' : start, 'length' : lng, 'mark' : mark})
                vbprint("MARK: start %d, length %d, mark '%s'", start, lng, mark)
                start = sz + marker2 + 4
            marker1 = line.find('(:::', marker2 + 4)

        vbprint("[%3d][[%s]]",sz,line[:-1])

        sz += len(line)
        flOut.write(line)

    if start > 0:
        lindex.append({'start' : start, 'length' : sz - start, 'mark' : ''})
        vbprint("LAST MARK: start %d, length %d, name ''", start, sz - start)

    return sz, lindex



def append2header(src, flHeader, var, mime, sz, arCompress):
    """Append the src file to the header file flHeader

    Parameters
    ----------
    src : str
        Source full file name
    flHeader : File
        Destination header file to append this new file
    var : str
        Variable name

    Returns
    -------
    sz : int
        size (length) of the output
    lindex : list
        List of markers in the input file and their position in the output file
    """

    lindex = []
    try:
        mm = mime.split('/')
        if mm[0] == "text" or mime == "application/javascript":
            fText = True
            bsize = 4096 # Read 4k blocks
            flSrc = open(src, 'rt')
            flHeader.write("\n\nconst char " + var + "[] PROGMEM = R\"=====(\n")
        else:
            fText = False
            bsize = 32 # Read only 32 bytes to simplify printing
            flSrc = open(src, 'rb')
            flHeader.write("\n\nconst uint8_t " + var + "[] PROGMEM = R{\n")

        if fText and mm[1] == "html":
            sz, lindex = process_html(flSrc, flHeader, arCompress)
        else: # Non-HTML files must be treated different
            while True:
                block = flSrc.read(bsize) # Just 4k blocks
                if not block:
                    break
                if fText:
                    flHeader.write(block)
                else:
                    flHeader.write(','.join('0x{:02X}'.format(b) for b in block) + ',\n')

        if fText:
            flHeader.write("\n)=====\";\n")
            if mm[1] == "html":
                generate_index(flHeader, var, sz, lindex)
        else:
            flHeader.write("};\n")
            flHeader.write("\n#define " + var + "_LENGTH  " + str(sz) + "\n")

        flSrc.close()

    except OSError as e:
        error(e, " while processing ", src," :",mime)

    return sz, lindex


def copy2header(src, dst, var, mime, sz, arCompress):
    """Copy and convert the src file into a C/C++ header file named dst

    Parameters
    ----------
    src : str
        Source full file name
    dst : str
        Destination header file
    var : str
        Variable name

    Returns
    -------
    Nothing
    """

    lindex = []
    try:
        flDst = open(dst, 'wt')
        flDst.write("#ifndef " + var.upper() + "\n#define " + var.upper())
        add_header(flDst, dst)

        sz, lindex = append2header(src, flDst, var, mime, sz, arCompress)

        flDst.write("\n#endif\n")
        flDst.close()

    except OSError as e:
        error(e, " while processing files", src,"=>",dst," :",mime)

    return sz, lindex


def copyflat(src, dst):
    """Copy the src file to the dst file treating them as binary files

    Parameters
    ----------
    src : str
        Source full file name
    dst : str
        Destination full file name

    Returns
    -------
    Nothing
    """

    try:
        flSrc = open(src, 'rb')
        flDst = open(dst, 'wb')
        while True:
            block = flSrc.read(4096) # Just 4k blocks
            if not block:
                break
            flDst.write(block)
        flSrc.close()
        flDst.close()

    except OSError as e:
        error(e, " while processing files", src,"=>",dst)


def copyhtml(src, dst, sz, arCompress):
    """Copy the src html file to the dst html file

    Parameters
    ----------
    src : str
        Source full file name
    dst : str
        Destination full file name

    Returns
    -------
    sz : int
        size (length) of the output
    lindex : list
        List of markers in the input file and their position in the output file
    """

    lindex = []
    try:
        flSrc = open(src, 'rt')
        flDst = open(dst, 'wt')

        sz, lindex = process_html(flSrc, flDst, arCompress)

        flSrc.close()
        flDst.close()

    except OSError as e:
        error(e, " while processing files", src,"=>",dst)

    return sz, lindex


def clonefile(src, dst, mime, sz, arCompress):
    """Clone the src into the dst creating directories as needed

    Parameters
    ----------
    src : str
        Source full file name
    dst : str
        Destination full file name

    Returns
    -------
    sz : int
        size (length) of the output
    lindex : list
        List of markers in the input file and their position in the output file
    """

    dstFolder = os.path.dirname(dst)
    if not os.path.exists(dstFolder):
        os.makedirs(dstFolder)
    if mime == 'text/html':
        return copyhtml(src, dst, sz, arCompress)
    else:
        copyflat(src, dst)
        return sz, []



def traverse_site(arPath, arOutput, arInclude, arType, extraIf, arCompress):
    """Traverse the directory structure of the site

    Parameters
    ----------
    arPath : str
        Path to the root directory of the site
    arOutput : str
        Path to the output directory (where output files will be written)
    arInclude : str
        File name for single output file
    arType : letter
        Type of generation

    Returns
    -------
    l : list
        Returns a list of file names
    """
 
    vbprint("Recursively from '",arPath, "', Output to '",arOutput, "', Single file='", 
            arInclude,"'\n\nTRAVERSE phase:",sep="")
    count = 0
    codelist = []
 
    if not os.path.exists(arOutput):
        os.makedirs(arOutput)

    if arType == "s":
        flSingleHeader = open(os.path.join(arOutput, arInclude),"wt")
        var = arInclude.replace(".","_")
        flSingleHeader.write("#ifndef " + var.upper() + "\n#define " + var.upper() + "\n")
        add_header(flSingleHeader, arInclude)

    # Get a list of all files in the site
    for rootDir, subdirs, filenames in os.walk(arPath):
        # process each file
        for filename in filenames:
            try:
                # fullName is the complete file name including the folder structure (full path)
                fullName=os.path.join(rootDir, filename)
                # nme is the file name without path or extension
                # ext is the file extension
                nme, ext = os.path.splitext(filename)
                # Ignore empty files, hiden files, and temprary files
                sz = os.stat(fullName).st_size
                if (sz == 0) or (ext == '.swp') or (len(nme) >0 and nme[0] == '.'):
                    vbprint("Ignored file:",fullName)
                    continue

                count += 1
                vbprint("SUBDirs=",subdirs,"rootDir=",rootDir,"fullName=",fullName,"filename=",filename)
                # root is the original path without the site folder arPath
                root = clean_dir(rootDir.replace(arPath,"",1))
                if filename == "index.html":
                    name  = root.replace(os.sep,"_") + "_html"
                    cname = root + ".html"
                    if not root:
                        name  = "index_html"
                        cname = "index.html"
                else: # filename.endswith(".html"):
                    name  = os.path.join(root,filename).replace(os.sep,"_")
                    cname = os.path.join(root,filename)
                if name.startswith("_"):
                    name  = name[1:]
                    cname = cname[1:]
                # fhtml is the client request path (for example in a html GET or a PUT)
                # it represents the resource in the server
                fhtml = "/" + cname
                # cname is the name of the cloned file into a new directory structure
                cname = os.path.join(arOutput,"data",clean_name(cname))
                name = name.replace(".","_")
                k = name.rfind("_")
                # fname is the filename with extension
                fname = clean_name(name[:k] + "." + name[k+1:])
                # ffname is the new name of the file when copied flat
                ffname = os.path.join(arOutput, "data", fname)
                # vname is the C/C++ variable name (const char) with the content of the file
                vname = re.sub(r'[^0-9a-zA-Z_]+', '_', name)
                if vname[0].isnumeric():
                    vname = "p" + name
                nm = vname.lower().split('_')
                vname = ""
                for n in nm:
                    vname += n.capitalize()
                extraIf.append(vname)
                # finame is name of include file containing the variable vname definition
                finame = clean_name(re.sub(r'[^0-9a-zA-Z_]+', '_', name) + ".h")
                if not root:
                    root = "/"
                    if nme == "index":
                        fhtml = root
                    else:
                        fhtml = root + filename
                elif filename == "index.html":
                    fhtml = root.replace(os.sep,'/') + '/'

                mime = mimetypes.MimeTypes().guess_type(fullName)[0]

                vbprint("NEW: name:'",name,"', fname:'",fname,"', ffname:'",ffname,"', vname:'",
                        vname,"', finame:'",finame,"', cname:'",cname,"', html:'",fhtml,
                        "', mime:'",mime,"'", sep="")
                
                if arType == "s":   # Append to a single header file
                    sz, lindex = append2header(fullName, flSingleHeader, vname, mime, sz, arCompress)
                elif arType == "m": # Generate a header file for each file
                    sz, lindex = copy2header(fullName, os.path.join(arOutput, finame), vname, 
                            mime, sz, arCompress)
                elif arType == "f": # Flatten the directory structure
                    sz, lindex = clonefile(fullName, ffname, mime, sz, arCompress)
                else: # arType == "c": # Clone folder structure
                    sz, lindex = clonefile(fullName, cname, mime, sz, arCompress)

                #########################################################
                # Examples:
                # 
                # 1- Main home page (public/index.html):
                # name:   index_html 
                # fname:  index.html  (flat file name)
                # vname:  IndexHtml   (const char var name)
                # finame: index_html.h           (header file name)
                # ffname: output/data/index.html (flat path name) 
                # cname:  output/data/index.html (clone path name) 
                # fhtml:  /
                # mime:   text/html
                # -------------------------------------------------------
                # 2- Error page (public/404.html):
                # name:   404_html 
                # fname:  404.html  (flat file name)
                # vname:  P404Html  (const char var name)
                # finame: 404_html.h           (header file name)
                # ffname: output/data/404.html (flat path name) 
                # cname:  output/data/404.html (clone path name) 
                # fhtml:  /404.html
                # mime:   text/html
                # -------------------------------------------------------
                # 3- Normal page (public/pages/sensors/index.html):
                # name:   pages_sensors_html 
                # fname:  pages_sensors.html  (flat file name)
                # vname:  PagesSensorsHtml    (const char var name)
                # finame: pages_sensors_html.h           (header file name)
                # ffname: output/data/pages_sensors.html (flat path name) 
                # cname:  output/data/pages/sensors.html (clone path name) 
                # fhtml:  /pages/sensors/
                # mime:   text/html
                # -------------------------------------------------------
                # 4- Other files (public/css/style.css):
                # name:   css_style_css 
                # fname:  css_style.css  (flat file name)
                # vname:  CssStyleCss    (const char var name)
                # finame: css_style_css.h           (header file name)
                # ffname: output/data/css_style.css (flat path name) 
                # cname:  output/data/css/style.css (clone path name) 
                # fhtml:  /css/style.css
                # mime:   text/css
                #########################################################
                codelist.append({'vname' : vname, 'ffname': ffname, 'finame' : finame, 'cname' : cname, 
                    'mime' : mime, 'html' : fhtml, 'size' : sz, 'index' : lindex})

            except OSError as e:
                error(e," while processing file", filename)

    if arType == "s":
        flSingleHeader.write("\n#endif\n")
        flSingleHeader.close()

    print("Number of processed files", count)
    return codelist


def arguments() :
    print("Usage:\n ",os.path.basename(sys.argv[0])," [flags]\n\nFlags:")
    print("   -d, --default         Use default folder paths (public and output)")
    print("   -h, --help            Prints this help")
    print("   -c, --compress        Compress html files by stripping spaces")
    print("   -i, --include <file>  Generates a single header that combines all the files")
    print("   -o, --output  <path>  Output folder path")
    print("   -p, --path    <path>  Folder path of the site to be converted")
    print("   -t, --type    <type>  type of output to be generated (default to f)")
    print("   -u, --use     <file>  Use this file as the generation template")
    print("       --if      <list>  list separated by commas of alphanumeric identifiers")
    print("   -w, --write   <file>  Write the internal generation template into file")
    print("   -v, --verbose         Produces verbose stdout ourput")
    print("\nGeneration types:")
    print("  m   Site files are embedded into header files as 'const char'.")
    print("      By default multiple header files will be generated, but using")
    print("      '--include <name>' forces a single include file named <name>.")
    print("  f   Copy the site files into the output path and rename them to")
    print("      flatten the folder structure into a single folder. Useful when")
    print("      hosting the site into a SPIFFS partition.")
    print("  c   Copy the site files into the output path maintaining the folder")
    print("      structure. Useful when hosting into a FAT or hierarchical partition.")
    sys.exit(2)


def main(argv):
   pdefault = 'public'
   odefault = 'output'
   fPathp = False
   fPatho = False
   nargs = 0

   # arguments:
   arPath = ""
   arOutput = ""
   arUse = ""
   arWrite = ""
   arInclude = ""
   arIf = ""
   arType = "f"
   arCompress = False

   try:
       opts, args = getopt.getopt(argv,"hp:do:i:vt:u:w:c",
               ["help","path=","output=","include=","default","verbose","type=","use=",
                   "write=","if=","compress"])
   except getopt.GetoptError as e:
      error(e)
      arguments()
   for opt, arg in opts:
      nargs += 1
      if (opt in ("-h","--help")) or (len(sys.argv) == 1):
         arguments()
      elif opt in ("-p", "--path"):
         arPath = arg
         fPathp =True 
      elif opt in ("-o", "--output"):
         arOutput = clean_dir(arg)
         fPatho = True
      elif opt in ("-u", "--use"):
         arUse = arg
      elif opt in ("-w", "--write"):
         arWrite = arg
      elif opt in ("-i", "--include"):
          arInclude = arg
      elif opt == "--if":
          arIf = arg
      elif opt in ("-t", "--type"):
          arType = arg
      elif opt in ("-d", "--default"):
          arPath = pdefault if(not fPathp) else arPath
          arOutput = odefault if(not fPatho) else arOutput
      elif opt in ("-v", "--verbose"):
          global verbose
          verbose = True
      elif opt in ("-c", "--compress"):
          arCompress = True
      elif opt == "": 
          error("Invalid argument")
          arguments()


   # Let now check that this makes sense
   if (not arWrite) and ((not arPath) or (not arOutput) or (not arType) or (nargs == 0)):
       error("Invalid combination of arguments")
       arguments()

   if len(arWrite) > 0:
       writetemplate(arWrite)

   if arPath and  arOutput and arType:
       if arType == "c":
           g = "(c) copying folder structure"
       elif arType == "f":
           g = "(f) copying files into a single flat folder"
       elif arType == "m":
           if not arInclude:
               g = "(m) encoding each file into a header file"
           else:
               g = "(m and -i) encoding all the files into " + arInclude
               arType = "s"
       else:
           error("Invalid type assignment (",arType,")")
           arguments()

       if (len(arInclude) > 0) and (arType != "s"):
           print("Ignoring --include due to incompatible --type")
           arInclude = ""

       extra = ""
       if arCompress:
           extra += "Compressing HTML files (removing leading spaces and empty lines)\n"

       if len(arUse) > 0:
           extra += "\n    Using " + arUse + " as the template"
       if len(arWrite) > 0:
           extra += "\n    Writing internal template to " + arWrite
       if not arIf:
           arIf = []
       else:
           arIf = arIf.split(',')
           while('' in arIf):
               arIf.remove('')

       # Check that arIf contains valid identifiers
       if ('NOT' in arIf) or ('OR' in arIf) or ('AND' in arIf):
           error("Boolean operators (AND, OR, NOT) not allow in --if list")
           sys.exit(2)
       if ('VARIABLES' in arIf) or ('FILES' in arIf) or ('HTML' in arIf):
           error("Keywords (FILES, VARIABLES, or HTML) not allow in --if list")
           sys.exit(2)
       for i in arIf:
           if not i.isalnum():
               error("Non alphanumeric entry on --if list:'",i,"'",sep="")
               sys.exit(2)

       if len(arIf) > 0:
           extra += "\n    Defining '" + ','.join(arIf) + "' as template conditionals"

       # These were not defined by the user, so don't print here
       extraIf = []
       if arType in ['f', 'c']:
           arIf.append('FILES')
       elif arType in ['s', 'm']:
           arIf.append('VARIABLES')

       print("Proceeding as follows:\n    Input folder:",arPath,"\n    Output folder:",arOutput,
               "\n    Generation type:",g,extra,"\n")

       #################################################################################
       # argDict is the dictionary of arguments + some extra info. Contains:
       #
       # argDict['lst'] : list of dictionaries
       #     list where each entry corresponds to the information for the original files in the site
       # argDict['arOutput'] : str (folder name)
       #     Path to the output directory (where output files will be written)
       # argDict['arInclude'] : str (file name)
       #     Name of the include file containing all the variables
       # argDict['arType'] : letter
       #     Type of generation
       # argDict['arUse'] : str (file name)
       #     Use arUse as the template instead of the internal template
       # argDict['arIf']: list
       #     List of tokens to use in if statements
       #################################################################################
       generate({'lst' : traverse_site(arPath,arOutput,arInclude,arType,extraIf,arCompress), 
           'arPath' : arPath, 'arOutput' : arOutput, 'arWrite' : arWrite, 'arOutput' : arOutput, 
           'arInclude' : arInclude, 'arType' : arType, 'arUse' :arUse, 'arIf' : arIf, 
           'arCompress' : arCompress},
           extraIf)

   print("done")

if __name__ == "__main__":
   main(sys.argv[1:])

# TODO:
# 1- parse and index embeded invocations in site files
# 2- for each site file, we need size, and a list of (start and lengh) pointers to the file (or to the const var)
#
# 2- Template todo:
#    a- sending a site html file stored in a const var ":::if VARIABLES"
#       a.1- when the const var has embedded markers "(:::<function-name>:::)"
#
#       server.setContentLength(CONTENT_LENGTH_UNKNOWN);
#       server.send ( 200, "text/html", first_part.c_str());
#       while (...) 
#       {
#         resp = "...";
#         server.sendContent(resp);
#       }
#
#       a.2- when the const var does not has embedded markers "(:::<function-name>:::)"
#            we still need to send the file in chunks no bigger than 5k
#
#    b- sending a site html file ":::if FILES" from the file system
#       b.1- that does not has embedded markers:
#
#       if( SPIFFS.exists(path))
#       {
#           File file = SPIFFS.open(path, "r");
#           size_t sent = server.streamFile(file, ":::MIME:::");
#           file.close();
#       }
#
#       b.2- if the html file has embedded markers "(:::<function-name>:::)", then we need to have a buffer and start loading the buffer and sending the file in pieces to process the markers. 
#
