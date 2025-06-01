LIST_APPLICATION_SIGNALS_SERVICES = {
    'name': 'list_application_signals_services',
    'description': '''
    <use_case>
      Use this tool to list AWS services returned from AWS CloudWatch Application Signal's ListServices API from the last 24 hours.
    </use_case>
    <important_notes>
        Expected Input: None

        Expected Output: A string formatted JSON information about services discovered by Application Signals, at most {default_max_services} services will be returned.
            - KeyAttributes may include:
                - Type: Designates the type of object this is.
                - ResourceType: Specifies the type of the resource. This field is used only when the value of the Type field is Resource or AWS::Resource.
                - Name: Specifies the name of the object. This is used only if the value of the Type field is Service, RemoteService, or AWS::Service.
                - Identifier: Identifies the resource objects of this resource. This is used only if the value of the Type field is Resource or AWS::Resource.
                - Environment: Specifies the location where this object is hosted, or what it belongs to.
            
            If an error is thrown, a string representing the error will be returned.      
    </important_notes>
    '''.format(default_max_services=100),
}

GET_SERVICE_DETAILS = {
    'name': 'get_service_details',
    'description': '''
    <use_case>
      Use this tool to get detailed information about a service discovered by Application Signals within the last 24 hours.
    </use_case>
    <important_notes>
        Expected Input: KeyAtrributes: dict
            KeyAttributes may include:
                - Type: Designates the type of object this is.
                - ResourceType: Specifies the type of the resource. This field is used only when the value of the Type field is Resource or AWS::Resource.
                - Name: Specifies the name of the object. This is used only if the value of the Type field is Service, RemoteService, or AWS::Service.
                - Identifier: Identifies the resource objects of this resource. This is used only if the value of the Type field is Resource or AWS::Resource.
                - Environment: Specifies the location where this object is hosted, or what it belongs to.

        Expected Output: A string formatted JSON about the given service pulled from the Application Signals API.
        
    </important_notes>
    ''',
}
