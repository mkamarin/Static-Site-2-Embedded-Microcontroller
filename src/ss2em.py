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
import datetime
import mimetypes

verbose = False

def vbprint(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)

def error(*args, **kwargs):
    print("ERROR:",*args, **kwargs, file = sys.stderr)

# This is internal template that guides the generation of the sample code
template = '''
START FILE
Arguments:

Path=[:::Path:::]
Output=[:::Output:::]
Use=[:::Use:::]
Write=[:::Write:::]
Include=[:::Include:::]
If=[:::If:::]
Type=[:::Type:::]
done

lets do includes
:::include

Now let do if OTA
:::if OTA
inside OTA 1
inside OTA 2
inside OTA  Now let do if BETA
:::if    BETA
Inside BETA
Let now do a for
:::for
Inside for
:::end
after for
:::fi
Inside OTA again
:::fi

:::for
Inside for a
Now let do if OTA
:::if OTA
In OTA
:::fi
  server.on("[:::HtmlPath:::]"; HTTP_GET; &get[:::Name:::]); 
  request->send_P(200; "[:::MIME:::]"; [:::Page:::]);
:::end

END of FILE
'''

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
        nm = frame['vname'].split('_')
        name = ""
        for n in nm:
            name += n.capitalize()
        return name
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
            line = flTemplate.readline()
            if not line:
                error("Template EOF within an :::if block")
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

    vbprint("IF BLOCK")
    while True:
        line = flTemplate.readline()
        if not line:
            error("Template EOF within an :::if block")
            break

        if line.startswith(":::fi"):
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

    vbprint("SKIP IF BLOCK")
    while True:
        line = flTemplate.readline()
        if not line:
            error("Template EOF within an :::if block")
            break

        if line.startswith(":::if"):
            skipif(line, flTemplate, flOutput, argDict, frame)
        elif line.startswith(":::fi"):
            return



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
    elif tokens[0] == ":::if":
        vbprint("Processing IF with",argDict['arIf'])
        if (len(tokens) > 0) and tokens[1] in argDict['arIf']:
            execif(line, flTemplate, flOutput, argDict, frame)
        else:
            skipif(line, flTemplate, flOutput, argDict, frame)
    elif tokens[0] == ":::for":
        vbprint("Processing FOR")
        execfor(line, flTemplate, flOutput, argDict)


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
            os.path.basename(sys.argv[0]) + " on " +  str(datetime.datetime.today()) + "\n//")


def generate(argDict):
    """Generate an example file for Arduino IDE

    Parameters
    ----------
    argDict   : dictionary of arguments
        Dictionary conating program arguments plus extra information

    Returns
    -------
    Nothing
    """

    fnName = os.path.join(argDict['arOutput'], argDict['arOutput'] + ".ino")
    vbprint("\nGENERATION phase (into '", fnName,"')",sep="")
    if not argDict['arUse']:
        flTemplate = io.StringIO(template)
    else:
        flTemplate = open(argDict['arUse'], 'r')

    flOutput = open(fnName, 'w')
    add_header(flOutput, fnName)

    # Process template
    while True:
        line = flTemplate.readline()
        if not line:
            break

        if line.startswith(":::"):
            execute(line, flTemplate, flOutput, argDict, {})
        else:
            flOutput.write(genline(line, {}, argDict))

    flOutput.close()


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

    flWrite = open(arWrite, 'w')
    flWrite.write(template)
    flWrite.close()


def append2header(src, flSingleHeader, var, mime):
    """Append the src file to the header file flSingleHeader

    Parameters
    ----------
    src : str
        Source full file name
    flSingleHeader : File
        Destination header file to append this new file
    var : str
        Variable name

    Returns
    -------
    Nothing
    """


    mm = mime.split('/')
    if mm[0] == "text" or mime == "application/javascript":
        fText = True
        bsize = 4096 # Read 4k blocks
        flSrc = open(src, 'rt')
        flSingleHeader.write("\n\nconst char " + var + "[] PROGMEM = R\"=====(\n")
    else:
        fText = False
        bsize = 32 # Read only 32 bytes to simplify printing
        flSrc = open(src, 'rb')
        flSingleHeader.write("\n\nconst uint8_t " + var + "[] PROGMEM = R{\n")


    while True:
        block = flSrc.read(bsize) # Just 4k blocks
        if not block:
            break
        if fText:
            flSingleHeader.write(block)
        else:
            flSingleHeader.write(','.join('0x{:02X}'.format(b) for b in block) + ',\n')

    if fText:
        flSingleHeader.write("\n)=====\";\n")
    else:
        flSingleHeader.write("};\n")
    flSrc.close()


def copy2header(src, dst, var, mime):
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

    flDst = open(dst, 'wt')
    flDst.write("#ifndef " + var.upper() + "\n#define " + var.upper())
    add_header(flDst, dst)

    mm = mime.split('/')
    if mm[0] == "text" or mime == "application/javascript":
        fText = True
        bsize = 4096 # Read 4k blocks
        flSrc = open(src, 'rt')
        flDst.write("\n\nconst char " + var + "[] PROGMEM = R\"=====(\n")
    else:
        fText = False
        bsize = 32 # Read only 32 bytes to simplify printing
        flSrc = open(src, 'rb')
        flSrc.write("\n\nconst uint8_t " + var + "[] PROGMEM = R{\n")


    while True:
        block = flSrc.read(bsize) # Just 4k blocks
        if not block:
            break
        if fText:
            flDst.write(block)
        else:
            flDst.write(','.join('0x{:02X}'.format(b) for b in block) + ',\n')

    if fText:
        flDst.write("\n)=====\";\n\n#endif\n")
    else:
        flDst.write("};\n\n#endif\n")

    flSrc.close()
    flDst.close()


def copyflat(src,dst):
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

    flSrc = open(src, 'rb')
    flDst = open(dst, 'wb')
    while True:
        block = flSrc.read(4096) # Just 4k blocks
        if not block:
            break
        flDst.write(block)
    flSrc.close()
    flDst.close()


def clonefile(src,dst):
    """Clone the src into the dst creating directories as needed

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

    dstFolder = os.path.dirname(dst)
    if not os.path.exists(dstFolder):
        os.makedirs(dstFolder)
    copyflat(src,dst)



def traverse_site(arPath,arOutput,arInclude,arType):
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
 
    vbprint("Recursively from '",arPath, "', Output to '",arOutput, "', Single file='", arInclude,"'\n\nTRAVERSE phase:",sep="")
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
                if (os.stat(fullName).st_size == 0) or (ext == '.swp') or (len(nme) >0 and nme[0] == '.'):
                    vbprint("Ignored file:",fullName)
                    continue

                count += 1
                vbprint("SUBDirs=",subdirs,"rootDir=",rootDir,"fullName=",fullName,"filename=",filename)
                # root is the original path without the site folder arPath
                root = rootDir.replace(arPath,"",1)
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
                html = "/" + cname
                # cname is the name of the cloned file into a new directory structure
                cname = os.path.join(arOutput,"data",cname)
                name = name.replace(".","_")
                k = name.rfind("_")
                # fname is the filename with extension
                fname = name[:k] + "." + name[k+1:]
                # ffname is the new name of the file when copied flat
                ffname = os.path.join(arOutput, "data", fname)
                # vname is the C/C++ variable name (const char) with the content of the file
                vname = name
                if vname[0].isnumeric():
                    vname = "p" + name
                # finame is name of include file containing the variable vname definition
                finame = name + ".h"
                if not root:
                    root = "/"
                    if nme == "index":
                        html = root
                    else:
                        html = root + filename
                elif filename == "index.html":
                    html = root.replace(os.sep,'/') + '/'

                mime = mimetypes.MimeTypes().guess_type(fullName)[0]

                vbprint("NEW: name:'",name,"', fname:'",fname,"', ffname:'",ffname,"', vname:'",
                        vname,"', finame:'",finame,"', cname:'",cname,"', html:'",html,"', mime:'",mime,"'", sep="")
                if arType == "s":   # Append to a single header file
                    append2header(fullName, flSingleHeader, vname, mime)
                elif arType == "m": # Generate a header file for each file
                    copy2header(fullName, os.path.join(arOutput, finame), vname, mime)
                elif arType == "f": # Flatten the directory structure
                    clonefile(fullName, ffname)
                else: # arType == "c": # Clone folder structure
                    clonefile(fullName, cname)

                #########################################################
                # Examples:
                # 
                # 1- Main home page (public/index.html):
                # name:   index_html 
                # fname:  index.html  (flat file name)
                # vname:  index_html  (const char var name)
                # finame: index_html.h           (header file name)
                # ffname: output/data/index.html (flat path name) 
                # cname:  output/data/index.html (clone path name) 
                # html:   /
                # mime:   text/html
                # -------------------------------------------------------
                # 2- Error page (public/404.html):
                # name:   404_html 
                # fname:  404.html  (flat file name)
                # vname:  p404_html  (const char var name)
                # finame: 404_html.h           (header file name)
                # ffname: output/data/404.html (flat path name) 
                # cname:  output/data/404.html (clone path name) 
                # html:   /404.html
                # mime:   text/html
                # -------------------------------------------------------
                # 3- Normal page (public/pages/sensors/index.html):
                # name:   pages_sensors_html 
                # fname:  pages_sensors.html  (flat file name)
                # vname:  pages_sensors_html  (const char var name)
                # finame: pages_sensors_html.h           (header file name)
                # ffname: output/data/pages_sensors.html (flat path name) 
                # cname:  output/data/pages/sensors.html (clone path name) 
                # html:   /pages/sensors/
                # mime:   text/html
                # -------------------------------------------------------
                # 4- Other files (public/css/style.css):
                # name:   css_style_css 
                # fname:  css_style.css  (flat file name)
                # vname:  css_style_css  (const char var name)
                # finame: css_style_css.h           (header file name)
                # ffname: output/data/css_style.css (flat path name) 
                # cname:  output/data/css/style.css (clone path name) 
                # html:   /css/style.css
                # mime:   text/css
                #########################################################
                codelist.append({'vname' : vname, 'ffname': ffname, 'finame' : finame, 'cname' : cname, 
                    'mime' : mime, 'html' : html})

            except OSError:
                error("Error while processing file", filename)

    if arType == "s":
        flSingleHeader.write("\n#endif\n")
        flSingleHeader.close()

    print("Number of processed files", count)
    return codelist


def arguments() :
    print("Usage:\n ",sys.argv[0]," [flags]\n\nFlags:")
    print("   -d, --default         Use default folder paths (public and output)")
    print("   -h, --help            Prints this help")
    print("   -i, --include <file>  Generates a single header that combines all the files")
    print("   -o, --output  <path>  Output folder path")
    print("   -p, --path    <path>  Folder path of the site to be converted")
    print("   -t, --type    <type>  type of output to be generated (default to f)")
    print("   -u, --use     <file>  Use this file as the generation template")
    print("       --if      <list>  list separated by commas of template sections")
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

   try:
       opts, args = getopt.getopt(argv,"hp:do:i:vt:u:w:",
               ["help","path=","output=","include=","default","verbose","type=","use=","write=","if="])
   except getopt.GetoptError:
      arguments()
   for opt, arg in opts:
      nargs += 1
      if (opt in ("-h","--help")) or (len(sys.argv) == 1):
         arguments()
      elif opt in ("-p", "--path"):
         arPath = arg
         fPathp =True 
      elif opt in ("-arOutput", "--output"):
         arOutput = arg
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
      elif opt == "": 
          arguments()

   # Let now check that this makes sense
   if (not arWrite) and ((not arPath) or (not arOutput) or (not arType) or (nargs == 0)):
       arguments()

   if len(arWrite) > 0:
       writetemplate(arWrite)

   if not ((not arPath) or (not arOutput) or (not arType)):
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
           arInclude = ""

       extra = ""
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

       if arType in ['f', 'c']:
           arIf.append('FILES')
       elif arType in ['s', 'm']:
           arIf.append('VARIABLES')

       if len(arIf) > 0:
           extra += "\n    Defining '" + ','.join(arIf) + "' as template conditionals"

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
       generate({'lst' : traverse_site(arPath,arOutput,arInclude,arType), 'arPath' : arPath, 
           'arOutput' : arOutput, 'arWrite' : arWrite, 'arOutput' : arOutput, 
           'arInclude' : arInclude, 'arType' : arType, 'arUse' :arUse, 'arIf' : arIf})

   print("done")

if __name__ == "__main__":
   main(sys.argv[1:])
