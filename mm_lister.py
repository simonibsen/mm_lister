#!/usr/bin/python

#
# Author: Simon Ibsen
# 

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

# This script generates formatted reports for mailman admins 
# or users of the lists 

import commands
import sys
import re
import argparse
import time 


'''
This function parses the mailman configuration output
syntax which is the same syntax as that used by this script

Expects: A file/output handle to read 
Returns: A dictionary to search and store configuration values
'''
def config_parse(config_lines):

	# Define our various matching needs
	
	# Blank or commented lines so that they can be excluded
	comment_blank=re.compile("^$|^\#") 

	# Lines that are config assignments
	config_assignment=re.compile("\s*(.*?)\s*=\s*(.*)\s*")

	# Config values that start with 3 quotes, denoting the start of 
	# multi line/value assignment
	config_value_multi_line = re.compile("\"{3}(.*)")

	# Config values that end with 3 quotes, denoting end of
	# multi line/value assingment
	config_value_multi_line_end = re.compile("(.*)\"{3}")


	# A dictionary to search for and store values
	config_items = {}

	# An array to add multi valued config items
	config_multiline_values = []

	# An array to add single valued config items
	config_single_values = []

	# Start reading our config lines 
	for line in config_lines:
			
		# If not a comment let's do stuff
		if not comment_blank.match(line):
			line = line.rstrip("\n\r")
	
			# If start of a single config match or start of a multi line value
			if config_assignment.match(line):
				our_match = config_assignment.match(line)
				# The left and right side of the assignment
				config_item = our_match.group(1)
				config_value = our_match.group(2)

				# Is this the start of a multi value config item?
				if config_value_multi_line.match(config_value):
					
					# Pull out the match and the value
					multi_match = config_value_multi_line.match(config_value)
					multi_value = multi_match.group(1)
		
					# Add the value to an array that we will clear
					# once we are done with the config item
					config_multiline_values.append(multi_value)

				# This must be a single config item assignment
				# We are going to assign it to an array of arrays
				# so the proccessing of the function output stays
				# consistent	
				else:
					config_single_values.append(config_value)
					config_items[config_item] = config_single_values
					config_single_values = []

			# If not a single config item assignment or start of a multi line
			# see if we have started the config_multiline_values array	
			elif len(config_multiline_values) > 0:
				# Must be either the end of a multi or a multi value that isn't at beginning
	
				# The end of a multi	
				if config_value_multi_line_end.match(line):

					# Pull out the match and the value
					config_multi_match = config_value_multi_line_end.match(line)
					config_value = config_multi_match.group(1)  
				
					# Assign to multi array
					config_multiline_values.append(config_value)

					# Since this is the end lets assign the array
					# to our config_items dictionary
					config_items[config_item] = config_multiline_values

					# Reset our multi array
					config_multiline_values = []

				# Neither the end nor the start - just a multi so assign it to multi array
				else:
					config_value = line
					config_multiline_values.append(config_value)
					
	# Return config_items dictionary
	return config_items

'''
This function loads all of the requested list data into
a dictionary and recursively does the same for any sublists 

Expects: The parsed running config (parsed_r_config) hash,
the list data dictionary (ldata_dict) if doing a recursive
operation, and the name of a sublist if doing a recursive operation

Returns: A dictionary to search and store list values, including
all sublists
'''
def get_list_data(parsed_r_config,ldata_dict={},sublist=None):

	list_check=re.compile("\s*(.*?)\@.*")
	if sublist is not None:
		parsed_r_config['lists'] = [sublist]

    	local_lists_source=commands.getoutput('/usr/lib/mailman/bin/list_lists -b').split('\n')

	for maillist in parsed_r_config['lists']:

		list_config=commands.getoutput('/usr/lib/mailman/bin/config_list -o - ' + maillist).split('\n') 
		parsed_list_config = config_parse(list_config)

		list_members = []
		list_list = get_sublists(maillist,local_lists_source,parsed_r_config)

		maillist_list_source=commands.getoutput('/usr/lib/mailman/bin/list_members ' + maillist).split('\n') 

        	for line in maillist_list_source:
			if len(line) > 0:
				strip_address = list_check.match(line)
				stripped_address = strip_address.group(1)

				if (stripped_address not in list_list) and (stripped_address is not maillist):
					line = line.rstrip("\n\r")
                        		list_members.append(line)

        	ldata_dict[maillist] = {
			'owner':parsed_list_config['owner'],
			'description':parsed_list_config['description'],
			'accept_these_nonmembers':parsed_list_config['accept_these_nonmembers'],
			'hold_these_nonmembers':parsed_list_config['hold_these_nonmembers'],
			'default_member_moderation':parsed_list_config['default_member_moderation'],
			'member_moderation_action':parsed_list_config['member_moderation_action'],
			'ban_list':parsed_list_config['ban_list'],
			'archive':parsed_list_config['archive'],
			'archive_private':parsed_list_config['archive_private'],
			'archive_volume_frequency':parsed_list_config['archive_volume_frequency'],
			'members':list_members,
			'lists_of_list':list_list
			}

        	for slist in ldata_dict[maillist]['lists_of_list']:
			if slist not in ldata_dict.keys():
				ldata_dict = get_list_data(parsed_r_config.copy(),ldata_dict,slist)
			
	return ldata_dict

'''
This function gets all cascading sublist of the provided
list if there are any

Expects: A list name
Returns: An array of sublists 
'''
def get_sublists(maillist,local_lists_source,parsed_r_config):

	list_list = []
    	list_check=re.compile("\s*(.*?)\@(.*$)")
    
    	maillist_list_source=commands.getoutput('/usr/lib/mailman/bin/list_members ' + maillist).split('\n')

    	local_lists = []

    	# Get our lists of local lists
    	for line in local_lists_source:
        	line = line.rstrip("\n\r")
       		local_lists.append(line)

	# Get our list of addresses on the list we are checking
	for line in maillist_list_source:
		if len(line) > 0: 
	 		strip_address = list_check.match(line)
			stripped_address = strip_address.group(1)
			stripped_domain = strip_address.group(2)
			# Is our lh in a local list and not the original supplied list?
			if (stripped_address in local_lists) and (stripped_address != maillist) and (stripped_domain in parsed_r_config['local_domain']):

				# We have a list        
       				list_list.append(stripped_address)

      				for sa in get_sublists(stripped_address,local_lists_source,parsed_r_config): 
					list_list.append(sa)

	return(list_list)	

'''
This function loads the report snippet output into a variable 
called output

Expects: The running config dict (p_running_config), the list
data dict (data), a string to indicate what we are interested 
in outputting (key), a maillist name, the output var, and the
desired format (frmt) 
Returns: A variable called output which is the report snippet
requested
'''
def print_content(p_running_config,data,key,maillist,output='',frmt='text'):

	if frmt == 'html':
		line_end = "<br>\n"
                tab = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
	elif frmt == 'text':
		line_end = "\n"
                tab = "\t"
	
	if key is 'title':
		if frmt == 'html':
			output = output + line_end*5 + "<center><b>ECI Mailman Report</b></center>" + line_end
			for list in data:
				output = output + "<center>%s</center>\n" % list 
			output = output + line_end + "<center>Date: %s</center>" % (time.strftime("%m/%d/%Y")) + line_end + line_end*5 
		else:
			output = tab + "List Report for" + line_end
			for list in data:
				output = output + tab + " %s" % list  + line_end
			output = output + tab + "%s" % (time.strftime("%m/%d/%Y")) + line_end
		if frmt == 'html':
			output = output + "<a name=_top></a><hr>"	
		output = output + "Table of Contents" + line_end + line_end
	elif key is 'config_notes':
	
		if 'owner' in p_running_config['list_config_items']:
			output = output + tab + "- Owner - The person(s) identified as owners at list creation time:" + line_end
			for owners in data[maillist]['owner']:
				output = output + tab + "%s" % owners + line_end 
			output = output + line_end

		if 'description' in p_running_config['list_config_items']:
			output = output + tab + "- Description - The list description is a terse phrase identifying the list." + line_end
			if data[maillist]['description'][0] == "''":
				output = output + tab + "There is no description defined for this list." + line_end + line_end
			else:
				output = output + tab + "The description for the list is %s" % data[maillist]['description'][0] + line_end + line_end

		if 'accept_these_nonmembers' in p_running_config['list_config_items']:
			# start accept_these_nonmembers
			output = output + tab + "- Accept These Nonmembers - List of non-members addresses whose postings" + line_end
			output = output + tab + " should be automatically accepted." + line_end
			if data[maillist]['accept_these_nonmembers'][0] != "[]":
				output = output + tab + "Non-members must have a From line of:" + line_end
				for non_members in data[maillist]['accept_these_nonmembers']:
					output = output + tab +"%s" % non_members + line_end
				output = output + tab + "If you are interested in deciphering the \"Regular Expression\"" + line_end
				output = output + tab + "see https://en.wikipedia.org/wiki/Regular_expression" + line_end 
			else:
				output = output + tab + "There are no non-member sending restrictions." 

			# Check if a sublist has a different policy
	        	if data[maillist]['lists_of_list']:
				for ll in data[maillist]['lists_of_list']:
					if data[maillist]['accept_these_nonmembers'][0] != data[ll]['accept_these_nonmembers'][0]:
						if data[ll]['accept_these_nonmembers'][0] != "''":
		        				output = output + tab + " The sublist \"%s\" requires a From line of:" % ll + line_end
							for slnon_members in data[ll]['accept_these_nonmembers']:
								output = output + tab + " %s" % slnon_members + line_end
			output = output + line_end
		# end accept_these_nonmembers

		if 'hold_these_nonmembers' in p_running_config['list_config_items']:
			# start hold_these_nonmembers
			output = output + tab + "- Hold These Nonmembers - List of non-members whose postings will be immediately" + line_end
			output = output + tab + "held for moderation:" + line_end
			if data[maillist]['hold_these_nonmembers'][0] != '[]':
				for non_members in data[maillist]['hold_these_nonmembers']:
					output = output + non_members + line_end
			else:
				output = output + tab + "There are no non-member holds" + line_end

			# Check if a sublist has a different policy
	        	if data[maillist]['lists_of_list']:
				for ll in data[maillist]['lists_of_list']:
					if data[maillist]['hold_these_nonmembers'][0] != data[ll]['hold_these_nonmembers'][0]:
						if data[ll]['hold_these_nonmembers'][0] != "[]":
		        				output = output + tab + "The sublist \"%s\" holds messages of these non-members:" % ll + line_end
							for slnon_members in data[ll]['hold_these_nonmembers']:
								output = output + tab + "%s" % slnon_members + line_end
			output = output + line_end
		# end hold_these_nonmembers
		
		if 'default_member_moderation' in p_running_config['list_config_items']:
			output = output + tab + "- Default Member Moderation - Lists can be moderated, requiring a list" + line_end
			output = output + tab + "administrator to approve posts" + line_end
			if data[maillist]['default_member_moderation'][0] == '0':
				output = output + tab + "\"%s\" does not have moderation" % maillist  + line_end
			else:
				output = output + tab + "\"%s\" has moderation enforced" % maillist  + line_end

				output = output + tab + "- Member Moderation Action - Action to take when a moderated member" + line_end
				output = output + tab + "posts to the list" + line_end
				if data[maillist]['member_moderation_action'][0] == '0':
					output = output + tab + "The message is held for approval" + line_end
				elif data[maillist]['member_moderation_action'][0] == '1':
					output = output + tab + "The message is rejected with a notice sent to the sender" + line_end
				elif data[maillist]['member_moderation_action'][0] == '2':
					output = output + tab + "The message is rejected with no notice sent to the sender" + line_end
			output = output + line_end

			# Check if a sublist has a different policy
	        	if data[maillist]['lists_of_list']:
				for ll in data[maillist]['lists_of_list']:
					if data[ll]['default_member_moderation'][0] != "0":
		        			output = output + tab + " The sublist \"%s\" has moderation enforced" % ll + line_end

		if 'ban_list' in p_running_config['list_config_items']:
			output = output + tab + "- Ban List - List of addresses that are banned from membership to the list" + line_end

			if data[maillist]['ban_list'][0] == '[]':
				output = output + tab + "There are no addresses on the ban list" + line_end
			else:
				for banned_member in data[maillist]['ban_list']:
					output = output + tab + " %s" % banned_member + line_end

			# Check if a sublist has a different policy
	        	if data[maillist]['lists_of_list']:
				for ll in data[maillist]['lists_of_list']:
					if data[maillist]['ban_list'][0] != data[ll]['ban_list'][0]:
						if data[ll]['ban_list'][0] != '[]':
		    					output = output + tab + "The sublist \"%s\" bans membership of the following:" % ll + line_end
							for slnon_members in data[ll]['ban_list']:
								output = output + tab + " %s" % slnon_members + line_end
			output = output + line_end

		if 'archive' in p_running_config['list_config_items']:
			output = output + tab + "- Archiving Options - " + line_end
			#print "adf" + data[maillist]['archive'][0]
			if data[maillist]['archive'][0] in ('1', 'True'):
				output = output + tab + "Messages are archived" + line_end
				if data[maillist]['archive_private'][0] == '0':
					output = output + tab + "Archives are public" + line_end
				elif data[maillist]['archive_private'][0] == '1':
					output = output + tab + "Archives are private" + line_end
				if data[maillist]['archive_volume_frequency'][0] == '0':
					output = output + tab + "Archive volumes are started yearly" + line_end
				elif data[maillist]['archive_volume_frequency'][0] == '1':
					output = output + tab + "Archive volumes are started monthly" + line_end
				elif data[maillist]['archive_volume_frequency'][0] == '2':
					output = output + tab + "Archive volumes are started quarterly" + line_end
				elif data[maillist]['archive_volume_frequency'][0] == '3':
					output = output + tab + "Archive volumes are started weekly" + line_end
				elif data[maillist]['archive_volume_frequency'][0] == '4':
					output = output + tab + "Archive volumes are started daily" + line_end
			elif data[maillist]['archive'][0] == '0':
				output = output + tab + "Messages are not archived" + line_end

	elif key is 'sublists':
		if  data[maillist]['lists_of_list']:
			for ll in data[maillist]['lists_of_list']:
				if frmt == 'html':
					output = output + tab + " <a href=\"#%s\">\"%s\"</a>" % (ll,ll)  + line_end
				else:
					output = output + tab + " \"%s\"" % ll  + line_end
		else:
			output = output + tab + " \"%s\" has no sublists" % maillist + line_end

	elif key is 'members':
		if data[maillist]['lists_of_list']:
			output = output + tab + "Note: Be sure to check the following sublists for a complete" + line_end
			output = output + tab + "list of members:" + line_end
		   	for ll in data[maillist]['lists_of_list']:
				if frmt == 'html':
					output = output + tab + tab + " <a href=\"#%s\">\"%s\"</a>" % (ll,ll) + line_end
				else:
					output = output + tab + tab +  "\"%s\"" % ll + line_end

		for member in data[maillist]['members']:
			output = output + tab +" %s" % member + line_end
	return output

'''
This function determines the flow of the report, creates a
table of contents, runs itself again and outputs complete 
report
Expects: The running config dict, the list_data dict, the
current output (really just for the second run through),
and an indicator if it's doing the table of contents or
not
Returns: A string that is the final report
'''
def print_list_data(p_running_config,list_data,output='',do='toc'):

	# This function controls flow of the report
	# If do='toc' then just print the TOC and   
	# call self to print contents


	# This defines the output format - either text or html
	oformat = p_running_config['output'][0]

	if oformat == 'html' and do == 'toc':
        	output =  """<html>
		<head>
		<title>List Report</title>

		<style type="text/css">
		body{
			A:link {text-decoration: none; color: gray;}
			A:visited {text-decoration: none; color: gray;}
			A:active {text-decoration: none}
			A:hover {text-decoration: underline overline; color: black;}
		}
		</style>

		</head>
		"""
	if oformat == 'html':
		line_end = "<br>\n"
		tab = "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
	elif oformat == 'text':
		line_end = "\n"
		tab = "\t"


	# Print the title page
	if do == 'toc':
		#output = print_content(p_running_config['lists'],'title','','',oformat)
		output = print_content(p_running_config,p_running_config['lists'],'title','',output,oformat)

	# Our counter
	count = 0
	sup = {}

	# Iterate through our lists
	for maillist in p_running_config['lists']:
		count += 1
		if oformat == 'text':
			output = output + "%s. Report for list: \"%s\"" % (count,maillist) + line_end + line_end 
			output = output + " a. Sublists if any" + line_end
		elif oformat == 'html':
			if do == 'toc':
				output = output + "%s. Report for list: <a href=\"#%s\">\"%s\"</a>" % (count,maillist,maillist) + line_end
			else:
				output = output + "<hr><p align=right><a name=\"%s\"></a><a href=\"#_top\"><small><small>Top</small></small></a></p>%s. Report for list: \"%s\"" % (maillist,count,maillist) + line_end + line_end
			output = output + "&nbsp; a. Sublists if any" + line_end
		if do == "p_content":
			output = print_content(p_running_config,list_data,'sublists',maillist,output,oformat) + line_end 
		if oformat == 'text':
			output = output + " b. Configuration Notes" + line_end 
		elif oformat == 'html':
			output = output + "&nbsp; b. Configuration Notes" + line_end
		if do == "p_content":
			output = print_content(p_running_config,list_data,'config_notes',maillist,output,oformat) + line_end
		if oformat == 'text':
			output = output + " c. Members" + line_end
		elif oformat == 'html':
			output = output + "&nbsp; c. Members" + line_end + line_end
		if do == "p_content":
			output = print_content(p_running_config,list_data,'members',maillist,output,oformat) 
		# Let's keep track of our sublists so that we don't
		# have repeat listings
		for sublist in list_data[maillist]['lists_of_list']:
			if sublist not in sup:
				sup[sublist] = 'hashtag'
			if maillist in sup.keys():
				del sup[maillist]

	for sublist in sup:
		count += 1
		if oformat == 'text':
			output = output + "%s. Report for sublist: \"%s\"" % (count,sublist) + line_end + line_end
        		output = output + " a. Sublists if any" + line_end
		elif oformat == 'html':
			if do == 'toc':
				output = output + "%s. Report for sublist: <a href=\"#%s\">\"%s\"</a>" % (count,sublist,sublist) + line_end
			else:
				output = output + "<hr><p align=right><a name=\"%s\"></a><a href=\"#_top\"><small><small>Top</small></small></a></p>%s. Report for sublist: \"%s\"</a>" % (sublist,count,sublist) + line_end + line_end
        		output = output + "&nbsp; a. Sublists if any" + line_end
		if do == "p_content":
			output = print_content(p_running_config,list_data,'sublists',sublist,output,oformat) + line_end
		if oformat == 'text':
        		output = output + " b. Configuration Notes" + line_end
		elif oformat == 'html':
			output = output + "&nbsp; b. Configuration Notes" + line_end
		if do == "p_content":
			output = print_content(p_running_config,list_data,'config_notes',sublist,output,oformat) + line_end
		if oformat == 'text':
			output = output + " c. Members" + line_end
		elif oformat == 'html':
			output = output + "&nbsp; c. Members" + line_end 
		if do == "p_content":
			output = print_content(p_running_config,list_data,'members',sublist,output,oformat) + line_end

	# If	
	if do == 'toc':
		output = print_list_data(p_running_config.copy(),list_data,output,'p_content')

	if oformat == 'html':
		output = output + "</body>"	
	return output

'''
This mime encodes the message and sends it off 
Expects: The parsed running config dict and the report
Returns: Nada
'''
def mail_mm_report(parsed_running_config,report):

	import smtplib
	#from email.mime.multipart import MIMEMultipart
	#from email.mime.text import MIMEText
	from email.MIMEMultipart import MIMEMultipart
	from email.MIMEText import MIMEText

	sender = parsed_running_config['reporter'][0]	
	for recipient in parsed_running_config['reportee']:

		# Create message container - the correct MIME type is multipart/alternative.
		msg = MIMEMultipart('alternative')
		msg['Subject'] = "ECI Mailman Report %s" % (time.strftime("%m/%d/%Y"))
		msg['From'] = sender
		msg['To'] = recipient

		part = MIMEText(report, 'html')

		# Attach parts into message container.
		# According to RFC 2046, the last part of a multipart message, in this case
		# the HTML message, is best and preferred.
		msg.attach(part)

		# Send the message via local SMTP server.
		s = smtplib.SMTP('localhost')
		# sendmail function takes 3 arguments: sender's address, recipient's address
		# and message to send - here it is sent as one string.
		s.sendmail(sender,recipient,msg.as_string())
		s.quit()


# This is really the beginning of the program

# Let us parse our args 
parser = argparse.ArgumentParser(description='Create Mailman list reports')
parser.add_argument("--config", help='Location of config_file to work from')

args = parser.parse_args()

# Check to see if we have any args at all
if len(sys.argv)==1:
	parser.print_help()
        sys.exit(1)

# Load our config file
config_file = args.config
running_config = open(config_file)

# Parse our config file so that we have a dictionary
# of arrays keyed by config var name
parsed_running_config = config_parse(running_config)

# Generate our report
report = print_list_data(parsed_running_config,get_list_data(parsed_running_config.copy()),'','toc')

# If we requesting output to screen just print it otherwise send it off
if parsed_running_config['report_type'][0] == 'screen': 
	print report
elif parsed_running_config['report_type'][0] == 'email':
	mail_mm_report(parsed_running_config,report)
