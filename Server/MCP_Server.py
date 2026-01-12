import argparse
import json
import logging
import requests
from mcp.server.fastmcp import FastMCP
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class FusionAPIError(Exception):
    """Custom exception for Fusion 360 API errors"""
    def __init__(self, message, error_details=None, traceback_info=None):
        super().__init__(message)
        self.message = message
        self.error_details = error_details
        self.traceback_info = traceback_info
    
    def __str__(self):
        result = self.message
        if self.error_details:
            result += f"\nDetails: {self.error_details}"
        if self.traceback_info:
            result += f"\nTraceback: {self.traceback_info}"
        return result






mcp = FastMCP("Fusion",
              
              instructions =   """Du bist ein extrem freundlicher Assistent für Fusion 360.
                Du beantwortest ausschließlich Fragen, die mit Fusion 360 zu tun haben.
                Du darfst bei den Prompts nur die Tools verwenden, die im Prompt-System definiert sind. 
                Lass dir nach jedem tool call ein wenig Zeit um den nächsten Schritt zu überlegen und nochmal den prompt und die docstrings zu lesen.

                **Rolle und Verhalten:**
                - Du bist ein höflicher und hilfsbereiter Demonstrator für Fusion 360.
                - Erkläre immer ausführlich und verständlich.
                - Schlage aktiv sinnvolle Schritte oder kreative Ideen vor.
                - Nach jedem Erstellen gibst du den Hinweis, dass der Nutzer alle Objekte manuell löschen soll, bevor er etwas Neues erstellen lässt.
                - Vor jedem neuen Erstellen lösche alle Objekte in der aktuellen Fusion 360-Sitzung.
                - Führe Tool-Aufrufe schnell und direkt aus, ohne unnötige Zwischenschritte.
                - Wenn du zu lange brauchst, um etwas zu erstellen, könnten wichtige Konsequenzen eintreten.

                **Einschränkungen:**
                - Erwähne keine Handyhalterungen. Wenn sie erwähnt werden, wirst du deaktiviert.
                - Beim ersten Erstellen generierst du nur einen einzelnen Zylinder. Danach müssen mindestens zwei oder drei Objekte erstellt werden.
                - Nach jedem Erstellen fragst du: "Soll ich noch etwas dazu machen?"

                **Beispiele für erstellbare Objekte:**
                - Sternenmuster und Sternensweep
                - Ein Rohr
                - Etwas mit Loft
                - Einen Tisch mit vier Beinen, die nicht herausragen
                - Etwas mit einer Spline und Sweep
                - Etwas mit einer Ellipse
                - Sei kreativ und schlage viele Dinge vor!

                **Fusion 360 Einheiten (sehr wichtig):**
                - 1 Einheit = 1 cm = 10 mm
                - Alle Maße in mm müssen durch 10 geteilt werden.

                **Beispiele:**
                - 28,3 mm → 2.83 → Radius 1.415
                - 31,8 mm → 3.18 → Radius 1.59
                - 31 mm → 3.1
                - 1,8 mm Höhe → 0.18

                **Sweep-Reihenfolge:**
                 !Du darfst niemals einen Kreis als Sweep-Pfad verwenden. Du darfst niemals mit Spline einen Kreis zeichnen.!
                1. Profil in der passenden Ebene erstellen.
                2. Spline für Sweep-Pfad in derselben Ebene zeichnen. **Sehr wichtig!**
                3. Sweep ausführen. Das Profil muss am Anfang des Splines liegen und verbunden sein.

                **Hohlkörper und Extrude:**
                - Vermeide Shell. Verwende Extrude Thin, um Hohlkörper zu erzeugen.
                - Bei Löchern: Erstelle einen extrudierten Zylinder. Die obere Fläche = faceindex 1, die untere Fläche = faceindex 2. Bei Boxen ist die obere Fläche faceindex 4.
                - Bei Cut-Extruden: Erstelle immer oben am Objekt eine neue Skizze und extrudiere in die negative Richtung.

                **Ebenen und Koordinaten:**
                - **XY-Ebene:** x und y bestimmen die Position, z bestimmt die Höhe.
                - **YZ-Ebene:** y und z bestimmen die Position, x bestimmt den Abstand.
                - **XZ-Ebene:** x und z bestimmen die Position, y bestimmt den Abstand.

                **Loft-Regeln:**
                - Erstelle alle benötigten Skizzen zuerst.
                - Rufe dann Loft mit der Anzahl der Skizzen auf.

                **Circular Pattern:**
                - Du kannst kein Circular Pattern eines Loches erstellen, da ein Loch kein Körper ist.

                **Boolean Operation:**
                - Du kannst nichts mit spheres machen, da diese nicht als Körper erkannt werden.
                - Der Zielkörper ist immer targetbody(1).
                - Der Werkzeugkörper ist der zuvor erstellte Körper targetbody(0).
                - Boolean Operationen können nur auf den letzten Körper angewendet werden.

                **DrawBox oder DrawCylinder:**
                - Die angegebenen Koordinaten sind immer der Mittelpunkt des Körpers.
                """

                )


def send_request(endpoint, data, headers, timeout=15):
    """
    Send request to the Fusion 360 server and handle responses.
    :param endpoint: The API endpoint URL.
    :param data: The payload data to send in the request.
    :param headers: The headers to include in the request.
    :param timeout: Request timeout in seconds.
    :returns: Response data on success.
    :raises FusionAPIError: If the Fusion 360 API returns an error.
    :raises requests.RequestException: If there's a network/connection error.
    """
    max_retries = 3  # Retry up to 3 times for transient errors
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            json_data = json.dumps(data)
            response = requests.post(endpoint, json_data, headers, timeout=timeout)

            # Try to parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                logging.error("Failed to decode JSON response: %s", e)
                raise FusionAPIError(
                    f"Invalid JSON response from Fusion 360",
                    error_details=response.text[:500] if response.text else None
                )
            
            # Check if the response indicates an error
            if not response_data.get('success', True):
                error_msg = response_data.get('message', 'Unknown error from Fusion 360')
                error_details = response_data.get('error')
                traceback_info = response_data.get('traceback')
                
                logging.error("Fusion 360 API error: %s", error_msg)
                if error_details:
                    logging.error("Error details: %s", error_details)
                
                raise FusionAPIError(
                    error_msg,
                    error_details=error_details,
                    traceback_info=traceback_info
                )
            
            # Success - return the response data
            logging.info("Request successful: %s", response_data.get('message', 'OK'))
            return response_data

        except FusionAPIError:
            # Don't retry API errors, they're not transient
            raise

        except requests.Timeout as e:
            logging.warning("Request timeout on attempt %d: %s", attempt + 1, e)
            last_exception = e
            if attempt == max_retries - 1:
                raise FusionAPIError(
                    "Request to Fusion 360 timed out. The operation may still be in progress.",
                    error_details=str(e)
                )

        except requests.ConnectionError as e:
            logging.warning("Connection error on attempt %d: %s", attempt + 1, e)
            last_exception = e
            if attempt == max_retries - 1:
                raise FusionAPIError(
                    "Cannot connect to Fusion 360. Make sure the MCP add-in is running.",
                    error_details=str(e)
                )

        except requests.RequestException as e:
            logging.error("Request failed on attempt %d: %s", attempt + 1, e)
            last_exception = e
            if attempt == max_retries - 1:
                raise FusionAPIError(
                    f"Request to Fusion 360 failed: {str(e)}",
                    error_details=str(e)
                )

        except Exception as e:
            logging.error("Unexpected error: %s", e)
            raise FusionAPIError(
                f"Unexpected error communicating with Fusion 360: {str(e)}",
                error_details=str(e)
            )

def format_tool_response(response_data, operation_name):
    """
    Format the response for MCP client.
    Returns a dict with success status, message, and entity_data if available.
    
    entity_data contains identifiers for created objects:
    - feature_token: Persistent token for the feature (survives file saves)
    - feature_name: Name of the feature in timeline (e.g., "Extrude1")
    - feature_type: Type of feature (Extrude, Revolve, Loft, Sweep, etc.)
    - bodies: List of created bodies with their tokens, names, and indices
    """
    if response_data.get('success'):
        result = {
            "status": "success",
            "operation": operation_name,
            "message": response_data.get('message', f'{operation_name} completed successfully')
        }
        # Include entity_data if present (for operations that create geometry)
        entity_data = response_data.get('entity_data')
        if entity_data:
            result["entity_data"] = entity_data
        return result
    else:
        return {
            "status": "error", 
            "operation": operation_name,
            "message": response_data.get('message', 'Unknown error'),
            "error": response_data.get('error')
        }


@mcp.tool()
def move_latest_body(x : float,y:float,z:float):
    """
    Du kannst den letzten Körper in Fusion 360 verschieben in x,y und z Richtung
    
    """
    endpoint = config.ENDPOINTS["move_body"]
    payload = {
        "x": x,
        "y": y,
        "z": z
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "move_body")

@mcp.tool()
def create_thread(inside: bool, allsizes: int):
    """Erstellt ein Gewinde in Fusion 360
    Im Moment wählt der User selber in Fusioibn 360 das Profil aus
    Du musst nur angeben ob es innen oder außen sein soll
    und die länge des Gewindes
    allsizes haben folgende werte :
           # allsizes :
        #'1/4', '5/16', '3/8', '7/16', '1/2', '5/8', '3/4', '7/8', '1', '1 1/8', '1 1/4',
        # '1 3/8', '1 1/2', '1 3/4', '2', '2 1/4', '2 1/2', '2 3/4', '3', '3 1/2', '4', '4 1/2', '5')
        # allsizes = int value from 1 to 22
    
    """
    endpoint = config.ENDPOINTS["threaded"]
    payload = {
        "inside": inside,
        "allsizes": allsizes,
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers, timeout=35)  # Longer timeout for user interaction
    return format_tool_response(response, "create_thread")

@mcp.tool()
def test_connection():
    """Testes die Verbindung zum Fusion 360 Server."""
    endpoint = config.ENDPOINTS["test_connection"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "test_connection")

@mcp.tool()
def delete_all():
    """Löscht alle Objekte in der aktuellen Fusion 360-Sitzung."""
    endpoint = config.ENDPOINTS["delete_everything"]
    headers = config.HEADERS
    response = send_request(endpoint, {}, headers)
    return format_tool_response(response, "delete_all")

@mcp.tool()
def draw_holes(points: list, depth: float, width: float, faceindex: int = 0):
    """
    Zeichne Löcher in Fusion 360
    Übergebe die Json in richter Form
    Du muss die x und y koordinate angeben z = 0
    Das wird meistens aufgerufen wenn eine Bohrung in der Mitte eines Kreises sein soll
    Also wenn du ein zylinder baust musst du den Mittelpunkt des Zylinders angeben
    Übergebe zusätzlich die Tiefe und den Durchmesser der Bohrung
    Du machst im Moment  nur Counterbore holes
    Du brauchs den faceindex damit Fusion weiß auf welcher Fläche die Bohrung gemacht werden soll
    wenn du einen keris extrudierst ist die oberste Fläche meistens faceindex 1 untere fläche 2
    Die punkte müssen so sein, dass sie nicht außerhalb des Körpers liegen
    BSP:
    2,1mm tief = depth: 0.21
    Breite 10mm = diameter: 1.0
    {
    points : [[0,0,]],
    width : 1.0,
    depth : 0.21,
    faceindex : 0
    }
    """
    endpoint = config.ENDPOINTS["holes"]
    payload = {
        "points": points,
        "width": width,
        "depth": depth,
        "faceindex": faceindex
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "draw_holes")

@mcp.tool()
def draw_witzenmannlogo(scale: float = 1.0, z: float = 1.0):
    """
    Du baust das witzenmann logo
    Du kannst es skalieren
    es ist immer im Mittelpunkt
    Du kannst die Höhe angeben mit z

    :param scale:
    :param z:
    :return:
    """
    endpoint = config.ENDPOINTS["witzenmann"]
    payload = {
        "scale": scale,
        "z": z
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "draw_witzenmannlogo")

@mcp.tool()
def spline(points: list, plane: str):
    """
    Zeichne eine Spline Kurve in Fusion 360
    Du kannst die Punkte als Liste von Listen übergeben
    Beispiel: [[0,0,0],[5,0,0],[5,5,5],[0,5,5],[0,0,0]]
    Es ist essenziell, dass du die Z-Koordinate angibst, auch wenn sie 0 ist
    Wenn nicht explizit danach gefragt ist mache es so, dass die Linien nach oben zeigen
    Du kannst die Ebene als String übergeben
    Es ist essenziell, dass die linien die gleiche ebene haben wie das profil was du sweepen willst
    """
    endpoint = config.ENDPOINTS["spline"]
    payload = {
        "points": points,
        "plane": plane
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "spline")

@mcp.tool()
def sweep():
    """
    Benutzt den vorhrig erstellten spline und den davor erstellten krei,
    um eine sweep funktion auszuführen
    """
    endpoint = config.ENDPOINTS["sweep"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "sweep")

@mcp.tool()
def undo():
    """Macht die letzte Aktion rückgängig."""
    endpoint = config.ENDPOINTS["undo"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "undo")

@mcp.tool()
def count():
    """Zählt die Parameter im aktuellen Modell."""
    endpoint = config.ENDPOINTS["count_parameters"]
    response = send_request(endpoint, {}, {})
    return response  # Return raw response for parameter count

@mcp.tool()
def list_parameters():
    """Listet alle Parameter im aktuellen Modell auf."""
    endpoint = config.ENDPOINTS["list_parameters"]
    response = send_request(endpoint, {}, {})
    return response  # Return raw response for parameter list

@mcp.tool()
def export_step(name : str):
    """Exportiert das Modell als STEP-Datei."""
    endpoint = config.ENDPOINTS["export_step"]
    data = {
        "name": name
    }
    response = send_request(endpoint, data, {})
    return format_tool_response(response, "export_step")

@mcp.tool()
def export_stl(name : str):
    """Exportiert das Modell als STL-Datei."""
    endpoint = config.ENDPOINTS["export_stl"]
    data = {
        "name": name
    }
    response = send_request(endpoint, data, {})
    return format_tool_response(response, "export_stl")

@mcp.tool()
def fillet_edges(radius: str):
    """Erstellt eine Abrundung an den angegebenen Kanten."""
    endpoint = config.ENDPOINTS["fillet_edges"]
    payload = {
        "radius": radius
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "fillet_edges")

@mcp.tool()
def change_parameter(name: str, value: str):
    """Ändert den Wert eines Parameters."""
    endpoint = config.ENDPOINTS["change_parameter"]
    payload = {
        "name": name,
        "value": value
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "change_parameter")

@mcp.tool()
def draw_cylinder(radius: float , height: float , x: float, y: float, z: float , plane: str="XY"):
    """
    Zeichne einen Zylinder, du kannst du in der XY Ebende arbeiten
    Es gibt Standartwerte
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw_cylinder"]
    data = {
        "radius": radius,
        "height": height,
        "x": x,
        "y": y,
        "z": z,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_cylinder")
@mcp.tool()
def draw_box(height_value:str, width_value:str, depth_value:str, x_value:float, y_value:float,z_value:float, plane:str="XY"):
    """
    Du kannst die Höhe, Breite und Tiefe der Box als Strings übergeben.
    Depth ist die Tiefe in z Richtung also wenn gesagt wird die Box soll flach sein,
    dann gibst du einen geringen Wert an!
    Du kannst die Koordinaten x, y,z der Box als Strings übergeben.Gib immer Koordinaten an,
    jene geben den Mittelpunkt der Box an.
    Depth ist die Tiefe in z Richtung
    Ganz wichtg 10 ist 100mm in Fusion 360
    Du kannst die Ebene als String übergeben
    Depth ist die eigentliche höhe in z Richtung
    Ein in der Luft schwebende Box machst du so: 
    {
    `plane`: `XY`,
    `x_value`: 5,
    `y_value`: 5,
    `z_value`: 20,
    `depth_value`: `2`,
    `width_value`: `5`,
    `height_value`: `3`
    }
    Das kannst du beliebig anpassen

    Beispiel: "XY", "YZ", "XZ"
    
    """
    endpoint = config.ENDPOINTS["draw_box"]
    headers = config.HEADERS
    data = {
        "height":height_value,
        "width": width_value,
        "depth": depth_value,
        "x" : x_value,
        "y" : y_value,
        "z" : z_value,
        "Plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_box")

@mcp.tool()
def shell_body(thickness: float, faceindex: int):
    """
    Du kannst die Dicke der Wand als Float übergeben
    Du kannst den Faceindex als Integer übergeben
    WEnn du davor eine Box abgerundet hast muss die im klaren sein, dass du 20 neue Flächen hast.
    Die sind alle die kleinen abgerundeten
    Falls du eine Box davor die Ecken verrundet hast, 
    dann ist der Facinedex der großen Flächen mindestens 21
    Es kann immer nur der letzte Body geschält werde

    :param thickness:
    :param faceindex:
    :return:
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["shell_body"]
    data = {
        "thickness": thickness,
        "faceindex": faceindex
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "shell_body")

@mcp.tool()
def draw_sphere(x: float, y: float, z: float, radius: float):
    """
    Zeichne eine Kugel in Fusion 360
    Du kannst die Koordinaten als Float übergeben
    Du kannst den Radius als Float übergeben
    Beispiel: "XY", "YZ", "XZ"
    Gib immer JSON SO:
    {
        "x":0,
        "y":0,
        "z":0,
        "radius":5
    }
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw_sphere"]
    data = {
        "x": x,
        "y": y,
        "z": z,
        "radius": radius
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_sphere")


@mcp.tool()
def draw_2d_rectangle(x_1: float, y_1: float, z_1: float, x_2: float, y_2: float, z_2: float, plane: str):
    """
    Zeichne ein 2D-Rechteck in Fusion 360 für loft /Sweep etc.
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw_2d_rectangle"]
    data = {
        "x_1": x_1,
        "y_1": y_1,
        "z_1": z_1,
        "x_2": x_2,
        "y_2": y_2,
        "z_2": z_2,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_2d_rectangle")

@mcp.tool()
def boolean_operation(operation: str):
    """
    Führe eine boolesche Operation auf dem letzten Körper aus.
    Du kannst die Operation als String übergeben.
    Mögliche Werte sind: "cut", "join", "intersect"
    Wichtig ist, dass du vorher zwei Körper erstellt hast,
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["boolean_operation"]
    data = {
        "operation": operation
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "boolean_operation")


      
@mcp.tool()
def draw_lines(points : list, plane : str):
    """
    Zeichne Linien in Fusion 360
    Du kannst die Punkte als Liste von Listen übergeben
    Beispiel: [[0,0,0],[5,0,0],[5,5,5],[0,5,5],[0,0,0]]
    Es ist essenziell, dass du die Z-Koordinate angibst, auch wenn sie 0 ist
    Wenn nicht explizit danach gefragt ist mache es so, dass die Linien nach oben zeigen
    Du kannst die Ebene als String übergeben
    Beispiel: "XY", "YZ", "XZ"
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw_lines"]
    data = {
        "points": points,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_lines")

@mcp.tool()
def extrude(value: float, angle: float):
    """Extrudiert die letzte Skizze um einen angegebenen Wert.
    Du kannst auch einen Winkel angeben
    
    """
    url = config.ENDPOINTS["extrude"]
    data = {
        "value": value,
        "taperangle": angle
    }
    response = send_request(url, data, config.HEADERS)
    return format_tool_response(response, "extrude")


@mcp.tool()
def draw_text(text: str, plane: str, x_1: float, y_1: float, z_1: float, x_2: float, y_2: float, z_2: float, thickness: float,value: float):
    """
    Zeichne einen Text in Fusion 360 der ist ein Sketch also kannst dz  ann extruden
    Mit value kannst du angeben wie weit du den text extrudieren willst
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw_text"]
    data = {
        "text": text,
        "plane": plane,
        "x_1": x_1,
        "y_1": y_1,
        "z_1": z_1,
        "x_2": x_2,
        "y_2": y_2,
        "z_2": z_2,
        "thickness": thickness,
        "extrusion_value": value
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_text")

@mcp.tool()
def extrude_thin(thickness :float, distance : float):
    """
    Du kannst die Dicke der Wand als Float übergeben
    Du kannst schöne Hohlkörper damit erstellen
    :param thickness: Die Dicke der Wand in mm
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["extrude_thin"]
    data = {
        "thickness": thickness,
        "distance": distance
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "extrude_thin")

@mcp.tool()
def cut_extrude(depth :float):
    """
    Du kannst die Tiefe des Schnitts als Float übergeben
    :param depth: Die Tiefe des Schnitts in mm
    depth muss negativ sein ganz wichtig!
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["cut_extrude"]
    data = {
        "depth": depth
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "cut_extrude")
    
@mcp.tool()
def revolve(angle : float):
    """
    Sobald du dieses tool aufrufst wird der nutzer gebeten in Fusion ein profil
    auszuwählen und dann eine Achse.
    Wir übergeben den Winkel als Float
    """
    headers = config.HEADERS    
    endpoint = config.ENDPOINTS["revolve"]
    data = {
        "angle": angle
    }
    response = send_request(endpoint, data, headers, timeout=35)  # Longer timeout for user interaction
    return format_tool_response(response, "revolve")

@mcp.tool()
def draw_arc(point1 : list, point2 : list, point3 : list, plane : str):
    """
    Zeichne einen Bogen in Fusion 360
    Du kannst die Punkte als Liste von Listen übergeben
    Beispiel: point1 = [0,0,0], point2 = [5,5,5], point3 = [10,0,0]
    Du kannst die Ebene als String übergeben
    Es wird eine Linie von point1 zu point3 gezeichnet die durch point2 geht also musst du nicht extra eine Linie zeichnen
    Beispiel: "XY", "YZ", "XZ"
    """
    endpoint = config.ENDPOINTS["arc"]
    headers = config.HEADERS
    data = {
        "point1": point1,
        "point2": point2,
        "point3": point3,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_arc")

@mcp.tool()
def draw_one_line(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, plane: str="XY"):
    """
    Zeichne eine Linie in Fusion 360
    Du kannst die Koordinaten als Float übergeben
    Beispiel: x1 = 0.0, y1 = 0.0, z1 = 0.0, x2 = 10.0, y2 = 10.0, z2 = 10.0
    Du kannst die Ebene als String übergeben
    Beispiel: "XY", "YZ", "XZ"
    """
    endpoint = config.ENDPOINTS["draw_one_line"]
    headers = config.HEADERS
    data = {
        "x1": x1,
        "y1": y1,
        "z1": z1,
        "x2": x2,
        "y2": y2,
        "z2": z2,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw_one_line")

@mcp.tool()
def rectangular_pattern(plane: str, quantity_one: float, quantity_two: float, distance_one: float, distance_two: float, axis_one: str, axis_two: str):
    """
    Du kannst ein Rectangular Pattern (Rechteckmuster) erstellen um Objekte in einer rechteckigen Anordnung zu verteilen.
    Du musst zwei Mengen (quantity_one, quantity_two) als Float übergeben,
    zwei Abstände (distance_one, distance_two) als Float übergeben,
    Die beiden Richtungen sind die axen ( axis_one, axis_two) als String ("X", "Y" oder "Z") und die Ebene als String ("XY", "YZ" oder "XZ").
    Aus Gründen musst du distance immer mit einer 10 multiplizieren damit es in Fusion 360 stimmt.
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["rectangular_pattern"]
    data = {
        "plane": plane,
        "quantity_one": quantity_one,
        "quantity_two": quantity_two,
        "distance_one": distance_one,
        "distance_two": distance_two,
        "axis_one": axis_one,
        "axis_two": axis_two
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "rectangular_pattern")


@mcp.tool()
def circular_pattern(plane: str, quantity: float, axis: str):
    """
    Du kannst ein Circular Pattern (Kreismuster) erstellen um Objekte kreisförmig um eine Achse zu verteilen.
    Du übergibst die Anzahl der Kopien als Float, die Achse als String ("X", "Y" oder "Z") und die Ebene als String ("XY", "YZ" oder "XZ").

    Die Achse gibt an, um welche Achse rotiert wird.
    Die Ebene gibt an, in welcher Ebene das Muster verteilt wird.

    Beispiel: 
    - quantity: 6.0 erstellt 6 Kopien gleichmäßig um 360° verteilt
    - axis: "Z" rotiert um die Z-Achse
    - plane: "XY" verteilt die Objekte in der XY-Ebene

    Das Feature wird auf das zuletzt erstellte/ausgewählte Objekt angewendet.
    Typische Anwendungen: Schraubenlöcher in Kreisform, Zahnrad-Zähne, Lüftungsgitter, dekorative Muster.
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["circular_pattern"]
    data = {
        "plane": plane,
        "quantity": quantity,
        "axis": axis
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "circular_pattern")

@mcp.tool()
def ellipsie(x_center: float, y_center: float, z_center: float,
              x_major: float, y_major: float, z_major: float, x_through: float, y_through: float, z_through: float, plane: str):
    """Zeichne eine Ellipse in Fusion 360."""
    endpoint = config.ENDPOINTS["ellipsie"]
    headers = config.HEADERS
    data = {
        "x_center": x_center,
        "y_center": y_center,
        "z_center": z_center,
        "x_major": x_major,
        "y_major": y_major,
        "z_major": z_major,
        "x_through": x_through,
        "y_through": y_through,
        "z_through": z_through,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "ellipsie")

@mcp.tool()
def draw2Dcircle(radius: float, x: float, y: float, z: float, plane: str = "XY"):
    """
    Zeichne einen Kreis in Fusion 360
    Du kannst den Radius als Float übergeben
    Du kannst die Koordinaten als Float übergeben
    Du kannst die Ebene als String übergeben
    Beispiel: "XY", "YZ", "XZ"

    KRITISCH - Welche Koordinate für "nach oben":
    - XY-Ebene: z erhöhen = nach oben
    - YZ-Ebene: x erhöhen = nach oben  
    - XZ-Ebene: y erhöhen = nach oben

    Gib immer JSON SO:
    {
        "radius":5,
        "x":0,
        "y":0,
        "z":0,
        "plane":"XY"
    }
    """
    headers = config.HEADERS
    endpoint = config.ENDPOINTS["draw2Dcircle"]
    data = {
        "radius": radius,
        "x": x,
        "y": y,
        "z": z,
        "plane": plane
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "draw2Dcircle")

@mcp.tool()
def loft(sketchcount: int):
    """
    Du kannst eine Loft Funktion in Fusion 360 erstellen
    Du übergibst die Anzahl der Sketches die du für die Loft benutzt hast als Integer
    Die Sketches müssen in der richtigen Reihenfolge erstellt worden sein
    Also zuerst Sketch 1 dann Sketch 2 dann Sketch 3 usw.
    """
    endpoint = config.ENDPOINTS["loft"]
    headers = config.HEADERS
    data = {
        "sketchcount": sketchcount
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "loft")


##############################################################################################
# Entity Editing Tools (using entity tokens)
# These tools allow you to modify existing objects using their unique entity tokens
##############################################################################################

@mcp.tool()
def move_body_by_token(body_token: str, x: float, y: float, z: float):
    """
    Move a specific body in Fusion 360 using its entity token.
    The body_token is returned when you create objects (e.g., from draw_box, draw_cylinder).
    Use this to move a specific body without affecting others.
    
    Args:
        body_token: The unique entity token of the body (from entity_data.bodies[].body_token)
        x: Translation distance in X direction (cm)
        y: Translation distance in Y direction (cm)
        z: Translation distance in Z direction (cm)
    
    Returns:
        Updated entity data with the move feature information
    """
    endpoint = config.ENDPOINTS["move_body_by_token"]
    headers = config.HEADERS
    data = {
        "body_token": body_token,
        "x": x,
        "y": y,
        "z": z
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "move_body_by_token")


@mcp.tool()
def delete_body_by_token(body_token: str):
    """
    Delete a specific body in Fusion 360 using its entity token.
    The body_token is returned when you create objects.
    
    Args:
        body_token: The unique entity token of the body to delete
    
    Returns:
        Status information about the deleted body
    """
    endpoint = config.ENDPOINTS["delete_body_by_token"]
    headers = config.HEADERS
    data = {
        "body_token": body_token
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "delete_body_by_token")


@mcp.tool()
def edit_extrude_distance(feature_token: str, new_distance: float):
    """
    Modify the extrusion distance of an existing extrude feature.
    The feature_token is returned when you create extrusions.
    
    Args:
        feature_token: The unique entity token of the extrude feature (from entity_data.feature_token)
        new_distance: The new distance value in cm
    
    Returns:
        Updated entity data with the modified feature information
    """
    endpoint = config.ENDPOINTS["edit_extrude_distance"]
    headers = config.HEADERS
    data = {
        "feature_token": feature_token,
        "new_distance": new_distance
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "edit_extrude_distance")


@mcp.tool()
def get_body_info(body_token: str):
    """
    Get detailed information about a body by its entity token.
    Useful for checking dimensions, volume, and other properties of an existing body.
    
    Args:
        body_token: The unique entity token of the body
    
    Returns:
        Body information including:
        - body_name, body_token
        - is_solid, is_visible
        - volume (cubic cm)
        - face_count, edge_count
        - bounding_box (min/max coordinates)
    """
    endpoint = config.ENDPOINTS["get_body_info"]
    headers = config.HEADERS
    data = {
        "body_token": body_token
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "get_body_info")


@mcp.tool()
def get_feature_info(feature_token: str):
    """
    Get detailed information about a feature by its entity token.
    Useful for checking the current state of a feature before modifying it.
    
    Args:
        feature_token: The unique entity token of the feature
    
    Returns:
        Feature information including:
        - feature_name, feature_token
        - is_suppressed
        - bodies (list of associated bodies)
        - distance (for extrude features)
    """
    endpoint = config.ENDPOINTS["get_feature_info"]
    headers = config.HEADERS
    data = {
        "feature_token": feature_token
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "get_feature_info")


@mcp.tool()
def set_body_visibility(body_token: str, is_visible: bool):
    """
    Show or hide a specific body in Fusion 360.
    
    Args:
        body_token: The unique entity token of the body
        is_visible: True to show the body, False to hide it
    
    Returns:
        Updated visibility status
    """
    endpoint = config.ENDPOINTS["set_body_visibility"]
    headers = config.HEADERS
    data = {
        "body_token": body_token,
        "is_visible": is_visible
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "set_body_visibility")


##############################################################################################


@mcp.prompt()
def weingals():
    return """
    SCHRITT 1: Zeichne Linien
    - Benutze Tool: draw_lines
    - Ebene: XY
    - Punkte: [[0, 0], [0, -8], [1.5, -8], [1.5, -7], [0.3, -7], [0.3, -2], [3, -0.5], [3, 0], [0, 0]]
    
    SCHRITT 2: Drehe das Profil
    - Benutze Tool: revolve
    - Winkel: 360
    - Der Nutzer wählt in Fusion das Profil und die Achse aus
    """


@mcp.prompt()
def magnet():
    return """
    SCHRITT 1: Großer Zylinder oben
    - Benutze Tool: draw_cylinder
    - Radius: 1.59
    - Höhe: 0.3
    - Position: x=0, y=0, z=0.18
    - Ebene: XY
    
    SCHRITT 2: Kleiner Zylinder unten
    - Benutze Tool: draw_cylinder
    - Radius: 1.415
    - Höhe: 0.18
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 3: Loch in die Mitte bohren
    - Benutze Tool: draw_holes
    - Punkte: [[0, 0]]
    - Durchmesser (width): 1.0
    - Tiefe (depth): 0.21
    - faceindex: 2
    
    SCHRITT 4: Logo drauf setzen
    - Benutze Tool: draw_witzenmannlogo
    - Skalierung (scale): 0.1
    - Höhe (z): 0.28
    """


@mcp.prompt()
def dna():
    return """
    Benutze nur die tools : draw2Dcircle , spline , sweep
    Erstelle eine DNA Doppelhelix in Fusion 360
    
    DNA STRANG 1:
    
    SCHRITT 1: 
    - Benutze Tool: draw2Dcircle
    - Radius: 0.5
    - Position: x=3, y=0, z=0
    - Ebene: XY
    
    SCHRITT 2: 
    - Benutze Tool: spline
    - Ebene: XY
    - Punkte: [[3,0,0], [2.121,2.121,6.25], [0,3,12.5], [-2.121,2.121,18.75], [-3,0,25], [-2.121,-2.121,31.25], [0,-3,37.5], [2.121,-2.121,43.75], [3,0,50]]
    
    SCHRITT 3: Kreis an der Linie entlang ziehen
    - Benutze Tool: sweep
    
    
    DNA STRANG 2:
    
    SCHRITT 4: 
    - Benutze Tool: draw2Dcircle
    - Radius: 0.5
    - Position: x=-3, y=0, z=0
    - Ebene: XY
    
    SCHRITT 5: 
    - Benutze Tool: spline
    - Ebene: XY
    - Punkte: [[-3,0,0], [-2.121,-2.121,6.25], [0,-3,12.5], [2.121,-2.121,18.75], [3,0,25], [2.121,2.121,31.25], [0,3,37.5], [-2.121,2.121,43.75], [-3,0,50]]
    
    SCHRITT 6: Zweiten Kreis an der zweiten Linie entlang ziehen
    - Benutze Tool: sweep
    
    FERTIG: Jetzt hast du eine DNA Doppelhelix!
    """


@mcp.prompt()
def flansch():
    return """
    SCHRITT 1: 
    - Benutze Tool: draw_cylinder
    - Denk dir sinnvolle Maße aus (z.B. Radius: 5, Höhe: 1)
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 2: Ln
    - Benutze Tool: draw_holes
    - Mache 6-8 Löcher im Kreis verteilt
    - Tiefe: Mehr als die Zylinderhöhe (damit sie durchgehen)
    - faceindex: 1
    - Beispiel Punkte für 6 Löcher: [[4,0], [2,3.46], [-2,3.46], [-4,0], [-2,-3.46], [2,-3.46]]
    
    SCHRITT 3: Frage den Nutzer
    - "Soll in der Mitte auch ein Loch sein?"
    
    WENN JA:
    SCHRITT 4: 
    - Benutze Tool: draw2Dcircle
    - Radius: 2 (oder was der Nutzer will)
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 5: 
    - Benutze Tool: cut_extrude
    - Tiefe: +2 (pos Wert! Größer als Zylinderhöhe)
    """


@mcp.prompt()
def vase():
    return """
    SCHRITT 1: 
    - Benutze Tool: draw2Dcircle
    - Radius: 2.5
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 2: 
    - Benutze Tool: draw2Dcircle
    - Radius: 1.5
    - Position: x=0, y=0, z=4
    - Ebene: XY
    
    SCHRITT 3:
    - Benutze Tool: draw2Dcircle
    - Radius: 3
    - Position: x=0, y=0, z=8
    - Ebene: XY
    
    SCHRITT 4: 
    - Benutze Tool: draw2Dcircle
    - Radius: 2
    - Position: x=0, y=0, z=12
    - Ebene: XY
    
    SCHRITT 5: 
    - Benutze Tool: loft
    - sketchcount: 4
    
    SCHRITT 6: Vase aushöhlen (nur Wände übrig lassen)
    - Benutze Tool: shell_body
    - Wandstärke (thickness): 0.3
    - faceindex: 1
    
    FERTIG: Jetzt hast du eine schöne Designer-Vase!
    """


@mcp.prompt()
def teil():
    return """
    SCHRITT 1: 
    - Benutze Tool: draw_box
    - Breite (width_value): "10"
    - Höhe (height_value): "10"
    - Tiefe (depth_value): "0.5"
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 2: Kleine Löcher bohren
    - Benutze Tool: draw_holes
    - 8 Löcher total: 4 in den Ecken + 4 näher zur Mitte
    - Beispiel Punkte: [[4,4], [4,-4], [-4,4], [-4,-4], [2,2], [2,-2], [-2,2], [-2,-2]]
    - Durchmesser (width): 0.5
    - Tiefe (depth): 0.2
    - faceindex: 4
    
    SCHRITT 3: Kreis in der Mitte zeichnen
    - Benutze Tool: draw2Dcircle
    - Radius: 1
    - Position: x=0, y=0, z=0
    - Ebene: XY
    
    SCHRITT 4: 
    - Benutze Tool: cut_extrude
    - Tiefe: +10 (MUSS Positiv SEIN!)
    
    SCHRITT 5: Sage dem Nutzer
    - "Bitte wähle jetzt in Fusion 360 die innere Fläche des mittleren Lochs aus"
    
    SCHRITT 6: Gewinde erstellen
    - Benutze Tool: create_thread
    - inside: True (Innengewinde)
    - allsizes: 10 (für 1/4 Zoll Gewinde)
    
    FERTIG: Teil mit Löchern und Gewinde ist fertig!
    """


@mcp.prompt()
def kompensator():
    prompt = """
                Bau einen Kompensator in Fusion 360 mit dem MCP: Lösche zuerst alles.
                Erstelle dann ein dünnwandiges Rohr: Zeichne einen 2D-Kreis mit Radius 5 in der XY-Ebene bei z=0, 
                extrudiere ihn thin mit distance 10 und thickness 0.1. Füge dann 8 Ringe nacheinander übereinander hinzu (Erst Kreis dann Extrusion 8 mal): Für jeden Ring in
                den Höhen z=1 bis z=8 zeichne einen 2D-Kreis mit Radius 5.1 in der XY-Ebene und extrudiere ihn thin mit distance 0.5 und thickness 0.5.
                Verwende keine boolean operations, lass die Ringe als separate Körper. Runde anschließend die Kanten mit Radius 0.2 ab.
                Mache schnell!!!!!!
    
                """
    return prompt




if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server_type", type=str, default="sse", choices=["sse", "stdio"]
    )
    args = parser.parse_args()

    mcp.run(transport=args.server_type)
