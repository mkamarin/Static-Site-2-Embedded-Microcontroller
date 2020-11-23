# Static-Site-2-Embedded-Microcontroller
Converts an static site into an embedded web site to be hosted in a micro-controller.
Transform the site pages into an easy to embed format and generates a sample hosting application based on a template.
Although, I have used [Hugo](https://gohugo.io/) for this project, it could easily work with other static site generators like [Gatsby](https://www.gatsbyjs.com/), [Jekyll](https://jekyllrb.com/), [Docusaurus](https://v2.docusaurus.io/), etc.
The site pages are transformed by either encoding them into an include file or by coping and renaming them for easy use on SPIFFS, Flat or other persistent storage available in the micro-controller.
A sample template is provided for ESP32 and ESP8266, but templates for other micro-controllers are easy to create with the provided template pseudo language.
The goal of this project is to enable the automation of static web sites as part of a micro-controller application' continuous integration and continuous deployment (CI/CD) pipeline.
Details on this project can be found in my web site.

## Features
The features of this program include:

- Prepares static web site files for micro-controller's restrictive file storage. Supports four alternatives:
    - No file storage, in which case the files are encoded into the source code. This is done by generating C/C++ header include files. Two types are supported:
        - Each file is encoded into its own header file.
        - All the files are encoded into a single header file.
    - Flat file storage. Storage alternatives like the serial peripheral interface flash file system ([SPIFFS](https://github.com/pellepl/spiffs)) that are common in embedded systems.
    - Hierarchical file storage. Like the traditional  file allocation table ([FAT](https://en.wikipedia.org/wiki/File_Allocation_Table)), [FatFS](http://elm-chan.org/fsw/ff/00index_e.html) or [LittleFS](https://github.com/littlefs-project/littlefs)
- Generates a sample web site host application for the micro-controller. The sample host application should work in the Arduino IDE. It is based on a template that can be customized. 

## Program execution

### NAME

    **ss2em** - transforms a static web site into an embedded web site


### SYNOPSIS

    **ss2em** [*flags*]


### DESCRIPTION

    **ss2em** converts an static site into an embedded web site to be hosted in a micro-controller.
It transforms the site pages into an easy to embed format and generates a sample hosting application based on a template.

### OPTIONS
**Flags:**

  **-d**, **--default**
 Use default folder paths (public and output)

  **-h**, **--help**
 Prints this help

  **-i**, **--include** `<file>`
 Generates a single header that combines all the files

  **-o**, **--output**  `<path>`
 Output folder path

  **-p**, **--path**    `<path>`
 Folder path of the site to be converted

  **-t**, **--type**    `<type>`
 type of output to be generated (default to f). See description below on **Generation types**

  **-u**, **--use**     `<file>`
 Use this file as the generation template

  **--if**      `<list>`
 list separated by commas of alphanumeric identifiers 

  **-w**, **--write**   `<file>`
 Write the internal generation template into file

  **-v**, **--verbose**
 Produces verbose stdout ourput


**Generation types:**

  **m**  Site files are embedded into header files as 'const char'.  By default multiple header files will be generated, but using `--include <name>` forces a single include file named `<name>`.
Adds `VARIABLES` to the `--if` flag. 

  **f**   Copy the site files into the output path and rename them to flatten the folder structure into a single folder. Useful when hosting the site into a SPIFFS partition.
Adds `FILES` to the `--if` flag.

  **c**  Copy the site files into the output path maintaining the folder
      structure. Useful when hosting into a FAT or hierarchical partition.
Adds `FILES` to the `--if` flag.

### EXAMPLES
**ss2em** -w template.txt

: Writes out to template.xt the internal template. This is useful to understand and modify the internal template

**ss2em** -u template.txt -if OTA,BETA -type m -p public -o web

 transform the files in the public folder and generates the output in the web folder.
The files are encoded into header files.
Uses template.txt (instead of the internal template) and define the OTA and BETA Boolean used in the template.txt for conditional generation.

**ss2em** -d

 transform the files in the public folder and generates the output in an output folder.
The files are flatten in the output folder.

### AUTHOR
Mike Marin

### COPYRIGHT
Copyright 2020 Mike Marin. 


## Templates
A template is a source file with embedded commands.
When those commands are expanded by ss2em, the source file should compiler.
For example, the internal template is a valid C/C++ file (with some ss2em commands).
After processing it with ss2em, you should be able to compile the generated file with the Arduino IDE and load it into a ESP32.

Note, when creating a template you should double scape any scaped character inside a C/C++ string.
For example: `"this is a two\nlines string"` must be written as `"this is a two\\nlines string"` (with two backslashes instead of one.)

### Template language
There are two types of embedded directives:

- Expansion directives or variables. 
These are tokens that are expanded in the output text when encounter.
They can appear anywhere in the text and have the form `[:::<variable>:::]` (start with a square bracket followed by three colons, the variable name followed by another three colons and a close square bracket.)
- Statements. These commands are executed and expanded in the output text. They can only appear at the start of a new line and have the form `:::<command>` (start the line with three colons followed by the command.)
The rest of the line is ignored.

#### Statements
Statements can be nested.
The statements supported are:
##### :::include
It will generate in the output text one or more C pre-processor #include statements. 
These statements are only needed (and will only be generated) when the flag `--type` was set to `f`, indicating that no file storage should be used, but instead the files should be encoded into one or more header files.
 
##### :::for
The `:::for` statement must end on a `:::end`.
The block of source code enclosed in between the `:::for` and the `:::end` will be expanded for each file in the input site (indicated with the `--path` flag.)
Each expansion of the `:::for` block will have the set of variables (`[:::HtmlPath:::], `[`:::MIME:::]`, `[:::Name:::]`, and `[:::Page:::]`) that corresponds to the file being processed.
Expanding those variables you can customize the generated code.

##### :::if `<condition>`
The `:::if` block must end in a `:::fi`.
The block of source code enclosed in between the `:::if` and the `:::fi` will be conditionally included in the output text.
The `:::if` statement test for a Boolean condition composed of identifiers and Boolean operators.
The valid Boolean operators are `AND`, `OR`, `NOT` and round parenthesis (`(` and `)`).
Note that Boolean operators must be in upper case.

The identifiers in the `:::if` condition are:

- identifiers defined by the `--if` flag
- internal generated identifiers

An identifier is True if is defined (either by a `--if` argument or internally), otherwise the identifier is considered False.

The internally generated identifiers are,

Value | Description
------|------------
VARIABLES | True when `--type` flag is either `'f'` or `'c'`, otherwise False.
FILES | True when `--type` flag is `'m'`, otherwise False.
HTML | True when the `[:::MIME:::]` type of the file being processed in a `:::for` statement is html, otherwise False
`<Name>` | True when `<Name>` equal to `[:::Name:::]` inside a `:::for` block for the file being processed, otherwise False.

##### :::# <comment>
Lines starting with `:::#` are considered comments and are removed from the output.
In most cases, you want to write comments in the host language (language in which the template was written), so these comments are exposed in the resulting output.
However, in some cases, you may want to comment on the generation statements (`:::<statement>`) or variables `[:::<name>:::]` 

#### Expansion directives or variables

Variable | Description
---------|------------
`[:::HtmlPath:::]` | Used inside a `:::For` statement. Expands to the http path of the page.
`[`:::MIME:::]`  | Used inside a `:::For` statement. Expands to the mime type of the page.
`[:::Name:::]` | Used inside a `:::For` statement. Expands a Name for the page that could be used to create variables or function names.
`[:::Page:::]` | Used inside a `:::For` statement. Expands to either a complete file name or the variable containing the page.
`[:::If:::]` | The execution argument for the flag `--if`
`[:::Include:::]` | The execution argument for the flag  `--include`
`[:::Output:::]` | The execution argument for the flag  `--output`
`[:::Path:::]` | The execution argument for the flag  `--path`
`[:::Type:::]` | The execution argument for the flag  `--type`
`[:::Use:::]` | The execution argument for the flag `--use`
`[:::Write:::]` | The execution argument for the flag  `--write`




