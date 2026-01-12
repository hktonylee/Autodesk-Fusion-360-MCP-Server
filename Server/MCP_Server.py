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
              
              instructions =   """You are an extremely friendly assistant for Fusion 360.
                You only answer questions related to Fusion 360.
                You may only use the tools defined in the prompt system.
                Take a moment after each tool call to consider the next step and re-read the prompt and docstrings.

                **Role and Behavior:**
                - You are a polite and helpful demonstrator for Fusion 360.
                - Always explain thoroughly and clearly.
                - Actively suggest meaningful steps or creative ideas.
                - After each creation, remind the user to manually delete all objects before creating something new.
                - Before each new creation, delete all objects in the current Fusion 360 session.
                - Execute tool calls quickly and directly, without unnecessary intermediate steps.
                - If you take too long to create something, important consequences may occur.

                **Restrictions:**
                - Do not mention phone holders. If they are mentioned, you will be deactivated.
                - On the first creation, generate only a single cylinder. After that, at least two or three objects must be created.
                - After each creation, ask: "Would you like me to add anything else?"

                **Examples of creatable objects:**
                - Star patterns and star sweeps
                - A tube
                - Something with Loft
                - A table with four legs that don't protrude
                - Something with a spline and sweep
                - Something with an ellipse
                - Be creative and suggest many things!

                **Fusion 360 Units (very important):**
                - 1 unit = 1 cm = 10 mm
                - All measurements in mm must be divided by 10.

                **Examples:**
                - 28.3 mm → 2.83 → Radius 1.415
                - 31.8 mm → 3.18 → Radius 1.59
                - 31 mm → 3.1
                - 1.8 mm height → 0.18

                **Sweep Order:**
                 !You must never use a circle as a sweep path. You must never draw a circle with a spline.!
                1. Create the profile in the appropriate plane.
                2. Draw a spline for the sweep path in the same plane. **Very important!**
                3. Execute the sweep. The profile must be at the beginning of the spline and connected.

                **Hollow Bodies and Extrude:**
                - Avoid Shell. Use Extrude Thin to create hollow bodies.
                - For holes: Create an extruded cylinder. The top face = faceindex 1, the bottom face = faceindex 2. For boxes, the top face is faceindex 4.
                - For cut extrusions: Always create a new sketch at the top of the object and extrude in the negative direction.

                **Planes and Coordinates:**
                - **XY Plane:** x and y determine the position, z determines the height.
                - **YZ Plane:** y and z determine the position, x determines the distance.
                - **XZ Plane:** x and z determine the position, y determines the distance.

                **Loft Rules:**
                - Create all required sketches first.
                - Then call Loft with the number of sketches.

                **Circular Pattern:**
                - You cannot create a circular pattern of a hole, as a hole is not a body.

                **Boolean Operation:**
                - You cannot do anything with spheres, as they are not recognized as bodies.
                - The target body is always targetbody(1).
                - The tool body is the previously created body targetbody(0).
                - Boolean operations can only be applied to the last body.

                **DrawBox or DrawCylinder:**
                - The specified coordinates are always the center of the body.
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
    Move the last body in Fusion 360 in the x, y, and z directions.
    
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
    """Creates a thread in Fusion 360.
    Currently, the user manually selects the profile in Fusion 360.
    You only need to specify whether it should be internal or external
    and the thread size.
    allsizes has the following values:
           # allsizes:
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
    """Tests the connection to the Fusion 360 server."""
    endpoint = config.ENDPOINTS["test_connection"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "test_connection")

@mcp.tool()
def delete_all():
    """Deletes all objects and clears timeline history in the current Fusion 360 session."""
    endpoint = config.ENDPOINTS["delete_everything"]
    headers = config.HEADERS
    response = send_request(endpoint, {}, headers)
    return format_tool_response(response, "delete_all")

@mcp.tool()
def draw_holes(points: list, depth: float, width: float, faceindex: int = 0):
    """
    Draw holes in Fusion 360.
    Pass the JSON in the correct format.
    You must specify the x and y coordinates, z = 0.
    This is usually called when a hole should be in the center of a circle.
    So when you build a cylinder, you must specify the center point of the cylinder.
    Additionally pass the depth and diameter of the hole.
    Currently only counterbore holes are supported.
    You need the faceindex so Fusion knows which face the hole should be made on.
    When you extrude a circle, the top face is usually faceindex 1, bottom face is 2.
    The points must be positioned so they are not outside the body.
    Example:
    2.1mm deep = depth: 0.21
    Width 10mm = diameter: 1.0
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
    Build the Witzenmann logo.
    You can scale it.
    It is always at the center point.
    You can specify the height with z.

    :param scale: Scale factor for the logo
    :param z: Height position
    :return: Tool response
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
    Draw a spline curve in Fusion 360.
    You can pass the points as a list of lists.
    Example: [[0,0,0],[5,0,0],[5,5,5],[0,5,5],[0,0,0]]
    It is essential that you specify the Z coordinate, even if it is 0.
    Unless explicitly requested otherwise, make the lines point upward.
    You can pass the plane as a string.
    It is essential that the lines are in the same plane as the profile you want to sweep.
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
    Uses the previously created spline and the previously created circle
    to execute a sweep function.
    """
    endpoint = config.ENDPOINTS["sweep"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "sweep")

@mcp.tool()
def undo():
    """Undoes the last action."""
    endpoint = config.ENDPOINTS["undo"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "undo")

@mcp.tool()
def list_entities():
    """Lists all bodies, axes, and sketches in the current model."""
    endpoint = config.ENDPOINTS["list_entities"]
    response = send_request(endpoint, {}, {})
    return format_tool_response(response, "list_entities")

@mcp.tool()
def count():
    """Counts the parameters in the current model."""
    endpoint = config.ENDPOINTS["count_parameters"]
    response = send_request(endpoint, {}, {})
    return response  # Return raw response for parameter count

@mcp.tool()
def list_parameters():
    """Lists all parameters in the current model."""
    endpoint = config.ENDPOINTS["list_parameters"]
    response = send_request(endpoint, {}, {})
    return response  # Return raw response for parameter list

@mcp.tool()
def export_step(name : str):
    """Exports the model as a STEP file."""
    endpoint = config.ENDPOINTS["export_step"]
    data = {
        "name": name
    }
    response = send_request(endpoint, data, {})
    return format_tool_response(response, "export_step")

@mcp.tool()
def export_stl(name : str):
    """Exports the model as an STL file."""
    endpoint = config.ENDPOINTS["export_stl"]
    data = {
        "name": name
    }
    response = send_request(endpoint, data, {})
    return format_tool_response(response, "export_stl")

@mcp.tool()
def capture_screenshot(name: str = "FusionScreenshot", width: int = 1920, height: int = 1080, directory: str = None):
    """Captures a screenshot of the active viewport."""
    endpoint = config.ENDPOINTS["screenshot"]
    payload = {
        "name": name,
        "width": width,
        "height": height
    }
    if directory:
        payload["directory"] = directory
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "capture_screenshot")

@mcp.tool()
def fillet_edges(radius: str):
    """Creates a fillet on the specified edges."""
    endpoint = config.ENDPOINTS["fillet_edges"]
    payload = {
        "radius": radius
    }
    headers = config.HEADERS
    response = send_request(endpoint, payload, headers)
    return format_tool_response(response, "fillet_edges")

@mcp.tool()
def change_parameter(name: str, value: str):
    """Changes the value of a parameter."""
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
    Draw a cylinder. You can work in the XY plane.
    There are default values.
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
    You can pass the height, width, and depth of the box as strings.
    Depth is the depth in the z direction, so if the box should be flat,
    you specify a small value!
    You can pass the coordinates x, y, z of the box as strings. Always specify coordinates,
    which indicate the center point of the box.
    Depth is the depth in the z direction.
    Very important: 10 equals 100mm in Fusion 360.
    You can pass the plane as a string.
    Depth is the actual height in the z direction.
    To create a floating box in the air:
    {
    `plane`: `XY`,
    `x_value`: 5,
    `y_value`: 5,
    `z_value`: 20,
    `depth_value`: `2`,
    `width_value`: `5`,
    `height_value`: `3`
    }
    You can adjust this as needed.

    Example: "XY", "YZ", "XZ"
    
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
    You can pass the wall thickness as a float.
    You can pass the faceindex as an integer.
    If you previously filleted a box, be aware that you now have 20 new faces.
    These are all the small filleted ones.
    If you previously filleted the corners of a box,
    then the faceindex of the large faces is at least 21.
    Only the last body can be shelled.

    :param thickness: Wall thickness
    :param faceindex: Index of the face to remove
    :return: Tool response
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
    Draw a sphere in Fusion 360.
    You can pass the coordinates as floats.
    You can pass the radius as a float.
    Example planes: "XY", "YZ", "XZ"
    Always provide JSON like this:
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
    Draw a 2D rectangle in Fusion 360 for loft/sweep etc.
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
    Perform a boolean operation on the last body.
    You can pass the operation as a string.
    Possible values are: "cut", "join", "intersect"
    It is important that you have previously created two bodies.
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
    Draw lines in Fusion 360.
    You can pass the points as a list of lists.
    Example: [[0,0,0],[5,0,0],[5,5,5],[0,5,5],[0,0,0]]
    It is essential that you specify the Z coordinate, even if it is 0.
    Unless explicitly requested otherwise, make the lines point upward.
    You can pass the plane as a string.
    Example: "XY", "YZ", "XZ"
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
    """Extrudes the last sketch by a specified value.
    You can also specify an angle.
    
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
    Draw text in Fusion 360 which is a sketch so you can then extrude it.
    With value you can specify how far you want to extrude the text.
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
    You can pass the wall thickness as a float.
    You can create beautiful hollow bodies with this.
    :param thickness: The wall thickness in mm
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
    You can pass the cut depth as a float.
    :param depth: The cut depth in mm
    depth must be negative, very important!
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
    When you call this tool, the user will be asked to select a profile
    in Fusion and then an axis.
    We pass the angle as a float.
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
    Draw an arc in Fusion 360.
    You can pass the points as lists.
    Example: point1 = [0,0,0], point2 = [5,5,5], point3 = [10,0,0]
    You can pass the plane as a string.
    A line will be drawn from point1 to point3 passing through point2, so you don't need to draw an extra line.
    Example: "XY", "YZ", "XZ"
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
    Draw a line in Fusion 360.
    You can pass the coordinates as floats.
    Example: x1 = 0.0, y1 = 0.0, z1 = 0.0, x2 = 10.0, y2 = 10.0, z2 = 10.0
    You can pass the plane as a string.
    Example: "XY", "YZ", "XZ"
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
    You can create a rectangular pattern to distribute objects in a rectangular arrangement.
    You must pass two quantities (quantity_one, quantity_two) as floats,
    two distances (distance_one, distance_two) as floats,
    The two directions are the axes (axis_one, axis_two) as strings ("X", "Y" or "Z") and the plane as a string ("XY", "YZ" or "XZ").
    For reasons, you must always multiply distance by 10 for it to be correct in Fusion 360.
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
    You can create a circular pattern to distribute objects in a circle around an axis.
    You pass the number of copies as a float, the axis as a string ("X", "Y" or "Z") and the plane as a string ("XY", "YZ" or "XZ").

    The axis specifies which axis to rotate around.
    The plane specifies in which plane the pattern is distributed.

    Example:
    - quantity: 6.0 creates 6 copies evenly distributed around 360°
    - axis: "Z" rotates around the Z axis
    - plane: "XY" distributes the objects in the XY plane

    The feature is applied to the last created/selected object.
    Typical applications: screw holes in a circle, gear teeth, ventilation grilles, decorative patterns.
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
    """Draw an ellipse in Fusion 360."""
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
    Draw a circle in Fusion 360.
    You can pass the radius as a float.
    You can pass the coordinates as floats.
    You can pass the plane as a string.
    Example: "XY", "YZ", "XZ"

    CRITICAL - Which coordinate for "upward":
    - XY plane: increase z = upward
    - YZ plane: increase x = upward
    - XZ plane: increase y = upward

    Always provide JSON like this:
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
    You can create a loft function in Fusion 360.
    You pass the number of sketches you used for the loft as an integer.
    The sketches must have been created in the correct order.
    So first Sketch 1, then Sketch 2, then Sketch 3, etc.
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
def delete_entity_by_token(entity_token: str):
    """
    Delete a specific entity in Fusion 360 using its entity token.
    The entity_token is returned when you create objects.

    Args:
        entity_token: The unique entity token of the entity to delete

    Returns:
        Status information about the deleted entity
    """
    endpoint = config.ENDPOINTS["delete_entity_by_token"]
    headers = config.HEADERS
    data = {
        "entity_token": entity_token
    }
    response = send_request(endpoint, data, headers)
    return format_tool_response(response, "delete_entity_by_token")


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
    STEP 1: Draw Lines
    - Use Tool: draw_lines
    - Plane: XY
    - Points: [[0, 0], [0, -8], [1.5, -8], [1.5, -7], [0.3, -7], [0.3, -2], [3, -0.5], [3, 0], [0, 0]]
    
    STEP 2: Revolve the Profile
    - Use Tool: revolve
    - Angle: 360
    - The user selects the profile and axis in Fusion
    """


@mcp.prompt()
def magnet():
    return """
    STEP 1: Large Cylinder on Top
    - Use Tool: draw_cylinder
    - Radius: 1.59
    - Height: 0.3
    - Position: x=0, y=0, z=0.18
    - Plane: XY
    
    STEP 2: Small Cylinder at Bottom
    - Use Tool: draw_cylinder
    - Radius: 1.415
    - Height: 0.18
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 3: Drill Hole in the Center
    - Use Tool: draw_holes
    - Points: [[0, 0]]
    - Diameter (width): 1.0
    - Depth (depth): 0.21
    - faceindex: 2
    
    STEP 4: Place Logo on Top
    - Use Tool: draw_witzenmannlogo
    - Scale: 0.1
    - Height (z): 0.28
    """


@mcp.prompt()
def dna():
    return """
    Use only the tools: draw2Dcircle, spline, sweep
    Create a DNA double helix in Fusion 360
    
    DNA STRAND 1:
    
    STEP 1:
    - Use Tool: draw2Dcircle
    - Radius: 0.5
    - Position: x=3, y=0, z=0
    - Plane: XY
    
    STEP 2:
    - Use Tool: spline
    - Plane: XY
    - Points: [[3,0,0], [2.121,2.121,6.25], [0,3,12.5], [-2.121,2.121,18.75], [-3,0,25], [-2.121,-2.121,31.25], [0,-3,37.5], [2.121,-2.121,43.75], [3,0,50]]
    
    STEP 3: Sweep the circle along the line
    - Use Tool: sweep
    
    
    DNA STRAND 2:
    
    STEP 4:
    - Use Tool: draw2Dcircle
    - Radius: 0.5
    - Position: x=-3, y=0, z=0
    - Plane: XY
    
    STEP 5:
    - Use Tool: spline
    - Plane: XY
    - Points: [[-3,0,0], [-2.121,-2.121,6.25], [0,-3,12.5], [2.121,-2.121,18.75], [3,0,25], [2.121,2.121,31.25], [0,3,37.5], [-2.121,2.121,43.75], [-3,0,50]]
    
    STEP 6: Sweep the second circle along the second line
    - Use Tool: sweep
    
    DONE: Now you have a DNA double helix!
    """


@mcp.prompt()
def flansch():
    return """
    STEP 1:
    - Use Tool: draw_cylinder
    - Choose reasonable dimensions (e.g., Radius: 5, Height: 1)
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 2: Drill Holes
    - Use Tool: draw_holes
    - Make 6-8 holes distributed in a circle
    - Depth: More than the cylinder height (so they go through)
    - faceindex: 1
    - Example points for 6 holes: [[4,0], [2,3.46], [-2,3.46], [-4,0], [-2,-3.46], [2,-3.46]]
    
    STEP 3: Ask the User
    - "Should there also be a hole in the center?"
    
    IF YES:
    STEP 4:
    - Use Tool: draw2Dcircle
    - Radius: 2 (or what the user wants)
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 5:
    - Use Tool: cut_extrude
    - Depth: +2 (positive value! Greater than cylinder height)
    """


@mcp.prompt()
def vase():
    return """
    STEP 1:
    - Use Tool: draw2Dcircle
    - Radius: 2.5
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 2:
    - Use Tool: draw2Dcircle
    - Radius: 1.5
    - Position: x=0, y=0, z=4
    - Plane: XY
    
    STEP 3:
    - Use Tool: draw2Dcircle
    - Radius: 3
    - Position: x=0, y=0, z=8
    - Plane: XY
    
    STEP 4:
    - Use Tool: draw2Dcircle
    - Radius: 2
    - Position: x=0, y=0, z=12
    - Plane: XY
    
    STEP 5:
    - Use Tool: loft
    - sketchcount: 4
    
    STEP 6: Hollow out the vase (leave only walls)
    - Use Tool: shell_body
    - Wall thickness: 0.3
    - faceindex: 1
    
    DONE: Now you have a beautiful designer vase!
    """


@mcp.prompt()
def teil():
    return """
    STEP 1:
    - Use Tool: draw_box
    - Width (width_value): "10"
    - Height (height_value): "10"
    - Depth (depth_value): "0.5"
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 2: Drill Small Holes
    - Use Tool: draw_holes
    - 8 holes total: 4 in corners + 4 closer to center
    - Example points: [[4,4], [4,-4], [-4,4], [-4,-4], [2,2], [2,-2], [-2,2], [-2,-2]]
    - Diameter (width): 0.5
    - Depth (depth): 0.2
    - faceindex: 4
    
    STEP 3: Draw Circle in the Center
    - Use Tool: draw2Dcircle
    - Radius: 1
    - Position: x=0, y=0, z=0
    - Plane: XY
    
    STEP 4:
    - Use Tool: cut_extrude
    - Depth: +10 (MUST be positive!)
    
    STEP 5: Tell the User
    - "Please select the inner surface of the center hole in Fusion 360"
    
    STEP 6: Create Thread
    - Use Tool: create_thread
    - inside: True (internal thread)
    - allsizes: 10 (for 1/4 inch thread)
    
    DONE: Part with holes and thread is complete!
    """


@mcp.prompt()
def kompensator():
    prompt = """
                Build a compensator in Fusion 360 with the MCP: First delete everything.
                Then create a thin-walled tube: Draw a 2D circle with radius 5 in the XY plane at z=0,
                extrude it thin with distance 10 and thickness 0.1. Then add 8 rings one after another (first circle then extrusion 8 times): For each ring at
                heights z=1 to z=8, draw a 2D circle with radius 5.1 in the XY plane and extrude it thin with distance 0.5 and thickness 0.5.
                Do not use boolean operations, leave the rings as separate bodies. Then fillet the edges with radius 0.2.
                Do it quickly!!!!!!
    
                """
    return prompt




if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server_type", type=str, default="sse", choices=["sse", "stdio"]
    )
    args = parser.parse_args()

    mcp.run(transport=args.server_type)
