# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
### BEGIN LICENSE
# This file is in the public domain
### END LICENSE

from locale import gettext as _

from gi.repository import Gtk , Gdk , GObject # pylint: disable=E0611
import logging
logger = logging.getLogger('shareviewer')

from shareviewer_lib import Window
from shareviewer.AboutShareviewerDialog import AboutShareviewerDialog
from shareviewer.PreferencesShareviewerDialog import PreferencesShareviewerDialog
import threading
import subprocess
import os
import time
import xml.etree.ElementTree as etree
from gi.repository.GdkPixbuf import Pixbuf
GObject.threads_init()

# See shareviewer_lib.Window.py for more details about how this class works
class ShareviewerWindow(Window):
    __gtype_name__ = "ShareviewerWindow"
    
    def finish_initializing(self, builder): # pylint: disable=E1002
        """Set up the main window"""
        super(ShareviewerWindow, self).finish_initializing(builder)

        self.AboutDialog = AboutShareviewerDialog
        self.PreferencesDialog = PreferencesShareviewerDialog

        # Code for other initialization actions should be added here.
        
        self.status_label = self.builder.get_object("status_label")
        self.device_label = self.builder.get_object("device_label")
        self.progressbar = self.builder.get_object("progressbar")
        self.text1 = self.builder.get_object("text1")
        self.text2 = self.builder.get_object("text2")
        self.button1 = self.builder.get_object("button1")
        self.button2 = self.builder.get_object("button2")
        
        self.mnu_open = self.builder.get_object("mnu_open")
        self.mnu_save = self.builder.get_object("mnu_save")
        self.mnu_clear = self.builder.get_object("mnu_clear")
        self.mnu_close = self.builder.get_object("mnu_close")
        
		self.mnu_clear.connect("activate",self.clear_scan)
		self.mnu_close.connect("activate",self.dispose) 
		self.mnu_save.connect("activate",self.save_scan) 
		self.mnu_open.connect("activate",self.open_scan) 
		     
        self.toolbar_open = self.builder.get_object("toolbar_open")
        self.toolbar_save = self.builder.get_object("toolbar_save")
        self.toolbar_clear = self.builder.get_object("toolbar_clear")
        self.toolbar_expand = self.builder.get_object("toolbar_expand")
        self.toolbar_collapse = self.builder.get_object("toolbar_collapse")
        self.toolbar_quit = self.builder.get_object("toolbar_quit")
        
        self.toolbar_open.connect("clicked",self.open_scan)
        self.toolbar_save.connect("clicked",self.save_scan)
        
        self.home = os.getenv("HOME")
        
		if not (os.path.exists(self.home+"/.shareviewer/range")):
			mf = open(self.home+"/.shareviewer/range","w")
			mf.close()
			
		self.mf = open(self.home+"/.shareviewer/range","r")
		limit=[]
		try:
			limit = self.mf.readline().split(" ")
		except:
			print "Error"	
		if len(limit)<2:
			limit=["",""]		
		self.mf.close()	         
        self.toolbar_quit.connect("clicked",self.dispose)                
        self.combo = self.builder.get_object("combo")
        self.text1.set_text(limit[0])
		self.text2.set_text(limit[1].replace("\n",""))
		self.combo.set_active(0)
		self.scrolled_w = self.builder.get_object("scrolled_w")
		
		self.image_start = self.builder.get_object("image_start")
		label_start = Gtk.Label(" Start  ")
		hbox_start = Gtk.HBox(False,0)
		hbox_start.pack_start(self.image_start, False, False, 0)
		hbox_start.pack_start(label_start, False, False, 0)
		label_start.show()
		hbox_start.show()
		self.button1.add(hbox_start)
		
		self.button2.connect("clicked",self.stop_threading)
		
		image_stop = self.builder.get_object("image_stop")
		label_stop = Gtk.Label(" Stop  ")
		hbox_stop = Gtk.HBox(False,0)
		hbox_stop.pack_start(image_stop, False, False, 0)
		hbox_stop.pack_start(label_stop, False, False, 0)
		label_stop.show()
		hbox_stop.show()
		self.button2.add(hbox_stop)
		
		
		self.model = Gtk.TreeStore(Pixbuf,str,str,str,str)
		self.treeview = Gtk.TreeView(self.model)
		self.treeview.show()
		self.toolbar_expand.connect_object('clicked', Gtk.TreeView.expand_all,self.treeview)
		self.toolbar_collapse.connect_object('clicked', Gtk.TreeView.collapse_all,self.treeview)
		self.treeview.set_rules_hint(True)
		self.treeview.set_enable_tree_lines(False)	
		self.treeview.connect("row_activated",self.row_activated)
		self.scrolled_w.add(self.treeview)
		#self.model.set_sort_func(1, compare, int)
		header = ["IP Address","HostName","MAC Address","Response Time"]
		cols = [Gtk.TreeViewColumn(title) for title in header]
		
		cells = [Gtk.CellRendererText() for i in range (len(header))]
		cell0 = Gtk.CellRendererPixbuf()
		cells.insert(0,cell0)
		for i,col in enumerate(cols) :
			col.set_min_width(200)
			
		self.treeview.append_column(cols[0])
		cols[0].pack_start(cells[0],0)	
		cols[0].pack_start(cells[1],0)	
		cols[0].set_attributes(cells[0],pixbuf=0)
		cols[0].set_attributes(cells[1],text=1)
		cols[0].set_sort_column_id(1)
		
		self.treeview.append_column(cols[1])
		cols[1].pack_start(cells[2],expand=True)	
		cols[1].set_attributes(cells[2],text=2)
		cols[1].set_sort_column_id(2)
		
		self.treeview.append_column(cols[2])
		cols[2].pack_start(cells[3],expand=True)	
		cols[2].set_attributes(cells[3],text=3)
		cols[2].set_sort_column_id(3)
		
		self.treeview.append_column(cols[3])
		cols[3].pack_start(cells[4],expand=True)	
		cols[3].set_attributes(cells[4],text=4)
		cols[3].set_sort_column_id(4)
		
		
        
    def on_button1_clicked(self,w):
		self.count=0
		self.devices=0
		self.status_label.set_text("Scanning...")
		self.progressbar.set_fraction(0.01)
		self.progressbar.set_text("0%")
		self.timer = GObject.timeout_add(100,self.progress_timeout)
		self.model.clear()
		range_start = self.text1.get_text()
		range_end   = self.text2.get_text()
		mf1 = open(self.home+"/.shareviewer/range","w")
		mf1.writelines(range_start+" "+range_end)
		mf1.close()
		start = range_start.split(".")
		end   = range_end.split(".")
		self.diff = int(end[3]) - int(start[3])+1
		self.no_of_threads=((int(end[3])-int(start[3]))/3)+1
		start1 = int(start[3])
		end1   = int(start[3])+3
		self.threads=[]
		for i in range(0,self.no_of_threads):
			flag=False
			if end1>int(end[3]):
				end1=int(end[3])+1
			t = threading.Thread(target=self.thread_scanning,args=(flag,start,start1,end1,))
			self.threads.append(t)
			t.start()
			start1+=3
			end1+=3	

    def thread_scanning(self,flag,ip_range,start,end):		         
		for i in range(int(start),int(end)):
			ip=ip_range[0]+"."+ip_range[1]+"."+ip_range[2]+"."+str(i)
			proc1 = subprocess.Popen("arping -c 1 "+ip+" | head -n 2 | tail -n 1 | awk '{print $5,$6}'" , shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
			
			proc = subprocess.Popen("smbclient -NL "+ip, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
			str1=["",""]
			for line in proc1.stdout:
				str1 = line.replace("[","").replace("]","").split(" ")
				if str1[0]=="broadcast(s))":
					proc2 = subprocess.Popen("ifconfig | head -n 1 | awk '{print $5}'", shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
					for line2 in proc2.stdout:
					    str1[0]=line2.upper()
					str1[1]="0ms"
			
			for line in proc.stderr:
				if('Domain' in line):
				    hostname =line[line.find("[")+1:line.find("]")]
				    if hostname=="WORKGROUP":
						proc_nmblookup = subprocess.Popen("nmblookup -A "+ip+" | head -n 2 | tail -n 1 | awk '{print $1 }'", shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
						for line in proc_nmblookup.stdout:
							hostname=line.replace("\n","").upper()
				    pixbuf = Pixbuf.new_from_file("/usr/share/shareviewer/media/computer.png")
				    self.devices+=1
				    par = self.model.append(None ,[pixbuf,ip.strip(),hostname,str1[0].replace("\n",""),str1[1].replace("ms"," ms").replace("\n","")])	
				    break;
			for line1 in proc.stdout:
				if line1.find("Disk")!=-1:
			         share=line1.strip().replace("Disk","").replace("Printer Drivers","").replace("Remote Admin","").replace("Default share","").replace("\n","")
			         pixbuf = Gtk.IconTheme.get_default().load_icon("gtk-directory", 16, 0)
			         child = self.model.append(par,[pixbuf,share,"","",""]) 
			self.count+=1

			
	def row_activated(self,tree,path,column):
		self.model = tree.get_model()
		if len(path)>1:
		    iter1 = self.model.get_iter(path)
		    share = self.model.get_value(iter1,1).strip().replace(" ","%20").replace("(","\(").replace(")","\)")
		    ip = self.model[path[0]][1]
		    file_manager = self.combo.get_active_text()
		    subprocess.Popen(file_manager+" smb://"+ip+"/"+share+"/", shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		if len(path)<=1:
			if tree.row_expanded(path):
				tree.collapse_row(path)
			else:	
				tree.expand_to_path(path)

	def progress_timeout(self):
		self.progressbar.set_fraction(self.count/float(self.diff))
		self.progressbar.set_text(str(int(self.count/float(self.diff)*100))+"%")
		self.device_label.set_text("Devices "+ str(self.devices))
		if self.progressbar.get_fraction()>=1:
			self.progressbar.set_text(" ")
			self.progressbar.set_fraction(0.01)
			self.status_label.set_text("Scan Complete")	 
				 
		return True

	def on_toolbar_clear_clicked(self,w):
		new_model = self.treeview.get_model()
		new_model.clear()
		self.devices=0
		self.device_label.set_text("Devices 0")
		self.status_label.set_text("Start Scan!")
		

	def stop_threading(self,w):
		try:
			for t in self.threads:
				t._Thread__stop()	
		except:
			print ""
			
	
	def dispose(self,w):
		try:
			for t in self.threads:
				t._Thread__stop()	
		except Exception as e:
			print ""
		Gtk.main_quit()

	def clear_scan(self,w):
		new_model = self.treeview.get_model()
		new_model.clear()
		self.devices=0
		self.device_label.set_text("Devices 0")
		self.status_label.set_text("Start Scan!")
		
	def save_scan(self,widget):
		chooser = Gtk.FileChooserDialog(title="Save current scan",action=Gtk.FileChooserAction.SAVE,buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CLOSE,Gtk.STOCK_SAVE,Gtk.ResponseType.OK))
		chooser.set_current_name("result "+time.strftime("%H:%M:%S %d-%m-%Y")+".xml")
		response = chooser.run()
		if response == Gtk.ResponseType.OK:
			file_name = chooser.get_filename()
			xml_file = open(file_name,"w")
			xml_file.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n")
			xml_file.write("<scan time=\""+time.strftime("%H:%M:%S %d-%m-%Y")+"\"" +" ip-start=\""+self.text1.get_text()+"\" ip-end=\""+self.text2.get_text()+"\">\n")
			for row in self.model:
				xml_file.write("<computer-node>\n")
				xml_file.write("<ip-address>"+row[1]+"</ip-address>\n")
				xml_file.write("<hostname>"+row[2]+"</hostname>\n")
				xml_file.write("<mac-address>"+row[3]+"</mac-address>\n")
				xml_file.write("<response-time>"+row[4]+"</response-time>\n")
				for child in row.iterchildren():
					xml_file.write("    <child>"+child[1].strip()+"</child>\n")
				xml_file.write("</computer-node>\n")
			xml_file.write("</scan>\n")
			
		chooser.destroy()	
		

	def open_scan(self,widget):
		try:
			chooser = Gtk.FileChooserDialog(title="Open an existing scan",action=Gtk.FileChooserAction.OPEN,buttons=(Gtk.STOCK_CANCEL,Gtk.ResponseType.CLOSE,Gtk.STOCK_OPEN,Gtk.ResponseType.OK))
			file_filter = Gtk.FileFilter()
			file_filter.set_name("All files")
			file_filter.add_pattern("*")
			filter1 = Gtk.FileFilter()
			filter1.set_name("xml    ")
			filter1.add_pattern("*.xml")
			chooser.add_filter(filter1)
			chooser.add_filter(file_filter)
			response = chooser.run()
			
			if response == Gtk.ResponseType.OK:
				file_name = chooser.get_filename()
				xmldoc = etree.parse(file_name)
				root = xmldoc.getroot()
				attributes = root.attrib
				self.text1.set_text(attributes["ip-start"])
				self.text2.set_text(attributes["ip-end"])
				self.model.clear()
				self.device_label.set_text(str(len(root)))
				pix_folder = Gtk.IconTheme.get_default().load_icon("gtk-directory", 16, 0)
				pix_computer = Pixbuf.new_from_file("/usr/share/shareviewer/media/computer.png")
				for node in root:
					ip_address = node.find("ip-address").text
					hostname = node.find("hostname").text
					mac_address = node.find("mac-address").text
					response_time = node.find("response-time").text
					par = self.model.append(None,[pix_computer,ip_address,hostname,mac_address,response_time])
					child = node.findall("child")
					for c in child:
						self.model.append(par,[pix_folder,c.text,"","",""])
		except Exception:
			chooser.destroy()
			error_dialog = self.builder.get_object("error_dialog")
			response = error_dialog.run()
			if response== -7 or response== -4:
				error_dialog.destroy()				
				
		chooser.destroy()		

def compare(model, row1, row2, user_data):
	sort_column, _ = model.get_sort_column_id()
	value1 = model.get_value(row1, sort_column)
	value2 = model.get_value(row2, sort_column)
	val1 = value1.split(".")
	val2 = value2.split(".")
	if len(val1)==4 and len(val2)==4:
		if int(val1[3]) < int(val2[3]):
			return -1
		elif int(val1[3]) == int(val2[3]):
			return 0
		else:
			return 1	
