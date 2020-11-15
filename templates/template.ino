

/****************************************
 * 
 * Program arguments:
 * Path='[:::Path:::]'
 * Output='[:::Output:::]'
 * Use='[:::Use:::]'
 * Write='[:::Write:::]'
 * Include='[:::Include:::]'
 * If='[:::If:::]'
 * Type='[:::Type:::]'
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
:::if OTA
#include <Update.h>
:::fi

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

:::if OTA
void postUpdateProcess(AsyncWebServerRequest *request, const String& filename, size_t index, uint8_t *data, size_t len, bool final)
{
    if(!index)
    {
        Serial.setDebugOutput(true);
        Serial.printf("\n[BEGIN] Update: '%s', index %d, len %d, %s\n", filename.c_str(), index, len, (final ? "DONE" : ""));
        cnt = 0;
        if (!Update.begin()) //start with max available size
        {
            Update.printError(Serial);
        }
    }

    if(((++cnt)%50)==0)Serial.printf("(%d, %d)\n", index, len); else Serial.print(".");

    if (Update.write(data, len) != len)
    {
        Update.printError(Serial);
    }

    if(final)
    {
        Serial.printf("(%d, %d)\n[END]\n", index, len);
        if (Update.end(true)) //true to set the size to the current progress
        {
            if(Update.hasError())
            {
                Serial.printf("Update Success: %u\nRebooting...\n", index+len);
            } 
            else 
            {
                Update.printError(Serial);
            }
        }
        Serial.setDebugOutput(false);
    }
}

void postUpdateEnd(AsyncWebServerRequest *request)
{
    Serial.println("done");
    if(Update.hasError())
    {
        String errStr = errPre_html;
        errStr += Update.errorString();
        errStr += errPost_html;
        request->send(500, "text/html", errStr.c_str());
    }
    else
    {
        request->send(200, "text/html", done_html);
      //ESP.restart();
    }
}
:::fi

#else // Non-Async

:::for files  
void get[:::Name:::](void)
{
    server.sendHeader("Connection", "close");
    server.send_P(200, "[:::MIME:::]", [:::Page:::]);
}
:::end

:::if OTA
void postUpdateProcess(void)
{
    HTTPUpload& upload = server.upload();
    switch (upload.status) 
    {
        case UPLOAD_FILE_START: 
            cnt = 0;
            Serial.printf("[BEGIN] Update: '%s'\n", upload.filename.c_str());
            if (!Update.begin()) //start with max available size
            {
                Update.printError(Serial);
            }
            break;

        case UPLOAD_FILE_WRITE: 
            if(((++cnt)%50)==0)Serial.println();
            Serial.print(".");
            if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) 
            {
                Update.printError(Serial);
            }
            break;

        case UPLOAD_FILE_END: 
            Serial.printf("\n[END]\n");
            if (Update.end(true)) //true to set the size to the current progress
            {
                Serial.printf("Update Success: %u\nRebooting...\n", upload.totalSize);
            } 
            else 
            {
                Update.printError(Serial);
            }
            Serial.setDebugOutput(false);
            break;

        default:
            Serial.printf("Update Failed Unexpectedly (likely broken connection): status=%d\n", upload.status);
    }
}

void postUpdateEnd(void)
{
    Serial.println("done");
    server.sendHeader("Connection", "close");
    if(Update.hasError())
    {
        String errStr = errPre_html;
        errStr += Update.errorString();
        errStr += errPost_html;
        server.send(500, "text/html", errStr.c_str());
    }
    else
    {
        server.send(200, "text/html", done_html);
      //ESP.restart();
    }
}
:::fi
#endif

void setup() 
{
  Serial.begin(115200);

  Serial.printf("\n=======\n\nSTART connecting to %s\n", ssid);
  WiFi.begin(ssid, password);
 
  Serial.println("Connecting to WiFi.");
  while (WiFi.status() != WL_CONNECTED) 
  {
    delay(500);
    Serial.print(".");
  } 

  String IP = WiFi.localIP().toString();
  Serial.printf("Connected to: %s\n IP address: %s\n Host name:  %s\n",
      ssid, IP.c_str(), WiFi.getHostname());

:::for files  
  server.on("[:::HtmlPath:::]", HTTP_GET, &get[:::Name:::]); 
:::end
:::if OTA
  server.on("/update", HTTP_GET, &getOTA); 
  server.on("/update", HTTP_POST, &postUpdateEnd, &postUpdateProcess);
:::fi
  server.begin();
}

void loop()
{
#ifndef USE_ASYNC
  server.handleClient();
  yield(1);
#endif
}
