from utils import MAX_SERVICES

MAP_SERVICES_BY_STATUS = {
    'name': 'map_services_by_status',
    'description': '''
    <use_case>
      Use this tool to categorize AWS services returned from AWS CloudWatch Application Signal's ListServices API into healthy and unhealthy status buckets based on their status.
    </use_case>

    <important_notes>
      1. start and end date inputs are given in ISO 8601 format. The start date has to be before the end date. 
         If an input is given for the start and end date, this tool will process services from within that time range.  
         If no input is given for the start and end date, this tool will process services from the last 24 hours. 
         Always explain to the user that you are processing services within that time range.
      
      2. max_services must be given as a positive integer value
         If an input is given for max services then only that many services will be processed so each bucket in the result will only have at most that many number of services.
         If no input is given for max services, this tool will list {default_max_services} services. 
         Always explain to the user that you are processing at most the number of max_services.
      
      3. If an error is thrown, a string representing the error will be returned.
    </important_notes>
    '''.format(default_max_services=MAX_SERVICES),
}
