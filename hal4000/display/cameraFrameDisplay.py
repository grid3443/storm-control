#!/usr/bin/python
#
## @file
#
# Camera frame display class.
#
# This class handles handles displaying camera data using the
# appropriate xCameraWidget class. It is also responsible for 
# displaying the camera record and shutter buttons.
#
# Hazen 09/15
#

from PyQt4 import QtCore, QtGui

# Debugging
import sc_library.hdebug as hdebug

# Camera Helper Modules
import qtWidgets.qtColorGradient as qtColorGradient
import qtWidgets.qtRangeSlider as qtRangeSlider

# Misc
import camera.feeds as feeds
import colorTables.colorTables as colorTables


## CameraFeedDisplay
#
# This class handles displaying feeds, e.g. "camera1", etc.
#
class CameraFeedDisplay(QtGui.QFrame):

    ## __init__
    #
    # Create a CameraFeedDisplay object. This object updates the image that it
    # displays at 10Hz.
    #
    # @param hardware The display part of a hardware object.
    # @param parameters A parameters object.
    # @param camera_display_ui A camera UI object as defined by a .ui file.
    # @param feed_name Which feed to use for this display ("camera1", "camera2", etc.).
    # @param parent (Optional) The PyQt parent of this object.
    #
    @hdebug.debug
    def __init__(self, hardware, parameters, camera_display_ui, feed_name, parent = None):
        QtGui.QFrame.__init__(self, parent)

        # General (alphabetically ordered).
        self.color_gradient = 0
        self.color_table = 0
        self.color_tables = colorTables.ColorTables("./colorTables/all_tables/")
        self.cycle_length = 0
        self.display_timer = QtCore.QTimer(self)
        self.feed_controller = False
        self.feed_name = feed_name
        self.filming = False
        self.frame = False
        self.max_intensity = parameters.get("max_intensity")
        self.parameters = parameters
        self.show_grid = 0
        self.show_info = 1
        self.show_target = 0

        # UI setup.
        self.ui = camera_display_ui
        self.ui.setupUi(self)

        self.ui.cameraScrollArea.setStyleSheet("QScrollArea { background-color: black } ")
        self.ui.rangeSlider = qtRangeSlider.QVRangeSlider(parent = self.ui.rangeSliderWidget)
        layout = QtGui.QGridLayout(self.ui.rangeSliderWidget)
        layout.addWidget(self.ui.rangeSlider)
        self.ui.rangeSlider.setGeometry(0, 0, self.ui.rangeSliderWidget.width(), self.ui.rangeSliderWidget.height())
        self.ui.rangeSlider.setRange([0.0, self.max_intensity, 1.0])
        self.ui.rangeSlider.setEmitWhileMoving(True)

        for color_name in self.color_tables.getColorTableNames():
            self.ui.colorComboBox.addItem(color_name[:-5])

        self.ui.gridAct = QtGui.QAction(self.tr("Show Grid"), self)
        self.ui.infoAct = QtGui.QAction(self.tr("Hide Info"), self)
        self.ui.targetAct = QtGui.QAction(self.tr("Show Target"), self)

        self.ui.syncLabel.hide()
        self.ui.syncSpinBox.hide()

        # Camera display widget.
        display_module = hardware.get("module_name")
        a_module = __import__('display.' + display_module, globals(), locals(), [display_module], -1)
        a_class = getattr(a_module, hardware.get("class_name"))
        self.camera_widget = a_class(parameters, parent = self.ui.cameraScrollArea)
        self.ui.cameraScrollArea.setWidget(self.camera_widget)

        self.ui.autoScaleButton.clicked.connect(self.handleAutoScale)
        self.ui.colorComboBox.currentIndexChanged.connect(self.handleColorTableChange)
        self.ui.gridAct.triggered.connect(self.handleGrid)
        self.ui.infoAct.triggered.connect(self.handleInfo)        
        self.ui.rangeSlider.doubleClick.connect(self.handleAutoScale)        
        self.ui.rangeSlider.rangeChanged.connect(self.handleRangeChange)
        self.ui.syncSpinBox.valueChanged.connect(self.handleSync)
        self.ui.targetAct.triggered.connect(self.handleTarget)

        # Display timer
        self.display_timer.setInterval(100)
        self.display_timer.timeout.connect(self.displayFrame)
        self.display_timer.start()
        
    ## contextMenuEvent
    #
    # This is called to create the popup menu when the use right click on the camera window.
    #
    # @param event A PyQt event object.
    #
    def contextMenuEvent(self, event):
        menu = QtGui.QMenu(self)
        menu.addAction(self.ui.infoAct)
        menu.addAction(self.ui.targetAct)
        menu.addAction(self.ui.gridAct)
        menu.exec_(event.globalPos())

    ## displayFrame
    #
    # This is called every 1/10th of a second to update the frame that is displayed.
    #
    def displayFrame(self):
        if self.frame:
            self.camera_widget.updateImageWithFrame(self.frame)
            
    ## getParameter
    #
    # This simplifies getting parameters from the current feed_controller.
    # Why? We use the feed_controller to access the parameters because the
    # desired behavior is that we will first see if the feed has the parameter. 
    # If it does not then we'll just use the value from the camera associated 
    # with the feed instead.
    #
    # @param pname The name of the parameter.
    # @param default_value (Optional) The value to return if the parameter is not found.
    #
    def getParameter(self, pname, default_value = None):
        return self.feed_controller.getFeedParameter(self.feed_name, pname, default_value)

    ## handleAutoScale
    #
    # Set the image display range automatically based on the current frames
    # minimum and maximum intensity.
    #
    # @param bool Dummy parameter.
    #
    @hdebug.debug
    def handleAutoScale(self, bool):
        [scalemin, scalemax] = self.camera_widget.getAutoScale()
        if scalemin < 0:
            scalemin = 0
        if scalemax > self.max_intensity:
            scalemax = self.max_intensity
        self.ui.rangeSlider.setValues([float(scalemin), float(scalemax)])

    ## handleColorTableChange
    #
    # Handles changing the color table used to display the image from the camera.
    #
    # @param index This parameter is ignored.
    #
    @hdebug.debug
    def handleColorTableChange(self, index):
        self.setParameter("colortable", 
                          str(self.ui.colorComboBox.currentText() + ".ctbl"))
        self.color_table = self.color_tables.getTableByName(self.getParameter("colortable"))
        self.camera_widget.newColorTable(self.color_table)
        self.color_gradient.newColorTable(self.color_table)
        
    ## handleGrid
    #
    # This handles telling the xCameraWidget to show or hide the grid
    # that is drawn on top of the current picture from the camera.
    #
    # @param boolean Dummy parameter.
    #
    @hdebug.debug
    def handleGrid(self, boolean):
        if self.show_grid:
            self.show_grid = 0
            self.ui.gridAct.setText("Show Grid")
        else:
            self.show_grid = 1
            self.ui.gridAct.setText("Hide Grid")
        self.camera_widget.setShowGrid(self.show_grid)

    ## handleInfo
    #
    # Handles telling the xCameraWidget to show or hide the
    # information display, ie. the location of the last mouse
    # click in camera pixels & the intensity of that camera pixel.
    #
    # @param boolean Dummy parameter.
    #
    @hdebug.debug
    def handleInfo(self, boolean):
        if self.show_info:
            self.show_info = 0
            self.ui.infoAct.setText("Show Info")
            self.ui.intensityPosLabel.hide()
            self.ui.intensityIntLabel.hide()
        else:
            self.show_info = 1
            self.ui.infoAct.setText("Hide Info")
            self.ui.intensityPosLabel.show()
            self.ui.intensityIntLabel.show()
        self.camera_widget.setShowInfo(self.show_info)

    ## handleIntensityInfo
    #
    # Handles displaying the intensity information that is 
    # received from the the xCameraWidget.
    #
    # @param x The x value of the pixel.
    # @param y The y value of the pixel.
    # @param i The intensity of the pixel.
    #
    def handleIntensityInfo(self, x, y, i):
        self.ui.intensityPosLabel.setText("({0:d},{1:d})".format(x, y, i))
        self.ui.intensityIntLabel.setText("{0:d}".format(i))

    ## handleRangeChange
    #
    # Handles a change in the display range as specified using the range slider.
    #
    # @param scale_min The camera pixel intensity that corresponds to 0.
    # @param scale_max The camera pixel intensity that corresponds to 255.
    #
    @hdebug.debug
    def handleRangeChange(self, scale_min, scale_max):
        if scale_max == scale_min:
            if scale_max < float(self.max_intensity):
                scale_max += 1.0
            else:
                scale_min -= 1.0
        self.setParameter("scalemax", int(scale_max))
        self.setParameter("scalemin", int(scale_min))
        self.updateRange()
        
    ## handleSync
    #
    # Handles setting the sync parameter. This parameter is used in
    # shutter sequences to specify which frame in the sequence should
    # be displayed, or just any random frame.
    #
    @hdebug.debug
    def handleSync(self, frame):
        self.setParameters("sync", frame)

    ## handleTarget
    #
    # Handles telling the xCameraWidget to show or hide the target
    # circle that is drawn in the center of the camera frame.
    #
    # @param boolean Dummy parameter.
    #
    @hdebug.debug
    def handleTarget(self, boolean):
        if self.show_target:
            self.show_target = 0
            self.ui.targetAct.setText("Show Target")
        else:
            self.show_target = 1
            self.ui.targetAct.setText("Hide Target")
        self.camera_widget.setShowTarget(self.show_target)

    ## newFeed
    #
    # This is called when the feed that we are supposed to display
    # is changed.
    #
    # @param feed_name The name of the new feed.
    #
    def newFeed(self, feed_name):
        self.feed_name = feed_name

        # Setup the camera display widget
        self.color_table = self.color_tables.getTableByName(self.getParameter("colortable"))
        self.camera_widget.newColorTable(self.color_table)
        self.updateRange()

        # color gradient
        if self.color_gradient:
            self.color_gradient.newColorTable(self.color_table)
        else:
            self.color_gradient = qtColorGradient.QColorGradient(colortable = self.color_table,
                                                                 parent = self.ui.colorFrame)
            layout = QtGui.QGridLayout(self.ui.colorFrame)
            layout.setMargin(2)
            layout.addWidget(self.color_gradient)

        self.ui.colorComboBox.setCurrentIndex(self.ui.colorComboBox.findText(self.getParameter("colortable")[:-5]))

        # general settings
        self.max_intensity = self.getParameter("max_intensity")
        self.ui.rangeSlider.setRange([0.0, self.max_intensity, 1.0])
        self.ui.rangeSlider.setValues([float(self.getParameter("scalemin")), 
                                       float(self.getParameter("scalemax"))])
        self.ui.syncSpinBox.setValue(self.getParameter("sync"))
        
    ## newFrame
    #
    # Handles new frame object from the camera control object. First it
    # checks that this frame is one that it should display (ie. "camera1",
    # "camera2", etc). If filming then a reference is kept to the appropriate
    # frame object to display. Otherwise a reference is kept to the most
    # recent frame object.
    #
    # @param frame A frame object.
    #
    def newFrame(self, frame):
        if (frame.which_camera == self.feed_name):
            if self.filming and self.getParameter("sync"):
                if((frame.number % self.cycle_length) == (self.getParameter("sync")-1)):
                    self.frame = frame
            else:
                self.frame = frame
                
    ## newParameters
    #
    # This is called when the current parameters change. It adjusts the various UI
    # and camera display settings to match those specified by the parameters object.
    #
    # @param parameters A parameters object.
    # @param feed_name The feed_name to use with these parameters.
    #
    @hdebug.debug
    def newParameters(self, parameters, feed_name):
        self.feed_controller = feeds.getFeedController(parameters)

        # Pass the parameters that are the same for all of the feeds
        # associated with a given camera to the camera_widget.
        self.camera_widget.newParameters(parameters.get(self.feed_controller.getCamera(feed_name)))

        # Configure for this feed.
        self.newFeed(feed_name)

    ## setParameter
    #
    # This simplifies setting parameters for the current feed_controller.
    #
    # @param pname The name of the parameter.
    # @param pvalue The new value.
    #
    def setParameter(self, pname, pvalue):
        self.feed_controller.setFeedParameter(self.feed_name, pname, pvalue)

    ## startFilm
    #
    # Called when filming starts to set the appropriate UI elements.
    #
    @hdebug.debug
    def startFilm(self, run_shutters):
        self.filming = True
        if run_shutters:
            self.ui.syncLabel.show()
            self.ui.syncSpinBox.show()

    ## stopFilm
    #
    # Called when filming stops to set the appropriate UI elements.
    #
    @hdebug.debug
    def stopFilm(self):
        self.filming = False
        self.ui.syncLabel.hide()
        self.ui.syncSpinBox.hide()

    ## updateRange
    #
    # This updates the text boxes that indicate the current range of
    # the display. It also updates the xCameraWidget with this range.
    #
    @hdebug.debug
    def updateRange(self):
        self.ui.scaleMax.setText(str(self.getParameter("scalemax")))
        self.ui.scaleMin.setText(str(self.getParameter("scalemin")))
        self.camera_widget.newRange([self.getParameter("scalemin"), self.getParameter("scalemax")])


## CameraFrameDisplay
#
# This class also handles interaction with the feeds, i.e. mouse drags,
# ROI selection etc. 
#
class CameraFrameDisplay(CameraFeedDisplay):
    cameraShutter = QtCore.pyqtSignal(str)
    dragMove = QtCore.pyqtSignal(str, float, float)
    dragStart = QtCore.pyqtSignal(str)
    feedChanged = QtCore.pyqtSignal(str)
    frameCaptured = QtCore.pyqtSignal(str, object)
    ROISelection = QtCore.pyqtSignal(str, object)

    ## __init__
    #
    # Create a CameraFrameDisplay object. This object updates the image that it
    # displays at 10Hz.
    #
    # @param hardware The display part of a hardware object.
    # @param parameters A parameters object.
    # @param camera_display_ui A camera UI object as defined by a .ui file.
    # @param feed_name Which feed to use for this display ("camera1", "camera2", etc.).
    # @param show_record Whether or not to show the record button.
    # @param parent (Optional) The PyQt parent of this object.
    #
    @hdebug.debug
    def __init__(self, hardware, parameters, camera_display_ui, default_feed, show_record, parent = None):
        CameraFeedDisplay.__init__(self, hardware, parameters, camera_display_ui, default_feed, parent)

        self.camera_widget.setDragEnabled(True)
        
        if not show_record:
            self.ui.recordButton.hide()
                
        # Signals
        self.camera_widget.displayCaptured.connect(self.handleDisplayCaptured)
        self.camera_widget.dragStart.connect(self.handleDragStart)
        self.camera_widget.dragMove.connect(self.handleDragMove)
        self.camera_widget.intensityInfo.connect(self.handleIntensityInfo)
        self.camera_widget.roiSelection.connect(self.handleROISelection)
        
        self.ui.cameraShutterButton.clicked.connect(self.handleCameraShutter)

    ## getRecordButton
    #
    # Return the record button element of the UI.
    #
    # @return The PyQt button that controls recording.
    #
    @hdebug.debug
    def getRecordButton(self):
        return self.ui.recordButton

    ## handleCameraShutter
    #
    @hdebug.debug
    def handleCameraShutter(self, boolean):
        if feeds.isCamera(self.feed_name):
            self.cameraShutter.emit(self.feed_name)

    ## handleDisplayCaptured
    #
    # @param a_pixmap A QPixmap object containing the image currently visible on the screen.
    #
    def handleDisplayCaptured(self, a_pixmap):
        self.frameCaptured.emit(self.feed_name, a_pixmap)

    ## handleDragStart
    #
    def handleDragStart(self):
        self.dragStart.emit(self.feed_name)

    ## handleDragMove
    #
    # This is just a pass-through for now. It might need to be buffered?
    #
    # @param x_disp x displacement in pixels.
    # @param y_disp y displacement in pixels.
    #
    def handleDragMove(self, x_disp, y_disp):
        self.dragMove.emit(self.feed_name, x_disp, y_disp)

    ## handleROISelection
    #
    # Handles roi selection from the xCameraWidget. Basically
    # this is a pass through that add camera information.
    #
    # @param select_rect The selection rectangle (QRect).
    #
    def handleROISelection(self, select_rect):
        self.ROISelection.emit(self.feed_name, select_rect)

    ## setSyncMax
    #
    # Sets the maximum value for the shutter synchronization spin box.
    #
    # @param sync_max The new maximum value for the spin box.
    #
    @hdebug.debug
    def setSyncMax(self, sync_max):
        self.cycle_length = sync_max
        self.ui.syncSpinBox.setMaximum(sync_max)

    ## startFilm
    #
    # Called when filming starts to set the appropriate UI elements.
    #
    @hdebug.debug
    def startFilm(self, run_shutters):
        CameraFeedDisplay.startFilm(self, run_shutters)
        self.ui.cameraShutterButton.setEnabled(False)

    ## stopFilm
    #
    # Called when filming stops to set the appropriate UI elements.
    #
    @hdebug.debug
    def stopFilm(self):
        CameraFeedDisplay.stopFilm(self)
        self.ui.cameraShutterButton.setEnabled(True)

    ## updateCameraProperties
    #
    # @param camera_properties A dictionary containing property sets for each camera.
    #
    @hdebug.debug
    def updateCameraProperties(self, camera_properties):
        if self.feed_name in camera_properties:
            if "have_shutter" in camera_properties[self.feed_name]:
                self.ui.cameraShutterButton.show()
            else:
                self.ui.cameraShutterButton.hide()
        else:
            self.ui.cameraShutterButton.hide()

    ## updatedParams
    #
    # For the display, only the shutter button state might have changed.
    #
    @hdebug.debug
    def updatedParams(self):
        if self.getParameter("shutter", False):
            self.ui.cameraShutterButton.setText("Close Shutter")
            self.ui.cameraShutterButton.setStyleSheet("QPushButton { color: green }")
        else:
            self.ui.cameraShutterButton.setText("Open Shutter")
            self.ui.cameraShutterButton.setStyleSheet("QPushButton { color: black }")

        
## CameraScollArea
#
# A slightly specialized QScrollArea. This scroll area lets the user 
# zoom in and pan around the images from the camera.
#
class CameraScrollArea(QtGui.QScrollArea):

    ## __init__
    #
    # Create a camera scroll area object.
    #
    # @param parent (Optional) The PyQt parent of this object.
    #
    def __init__(self, parent = None):
        QtGui.QScrollArea.__init__(self, parent)

        self.camera_widget = None
        self.magnification = 1

        self.h_scroll_bar = CameraScrollBar(self.horizontalScrollBar())
        self.v_scroll_bar = CameraScrollBar(self.verticalScrollBar())

    ## setWidget
    #
    # Sets the widget that will be displayed in the scroll area.
    #
    # @param camera_widget A xCameraWidget object.
    #
    def setWidget(self, camera_widget):
        QtGui.QScrollArea.setWidget(self, camera_widget)
        self.camera_widget = camera_widget

    ## wheelEvent
    #
    # Handles mouse wheel events.
    #
    # @param event A PyQt wheel event object.
    #
    def wheelEvent(self, event):
        if (event.delta() > 0):
            self.magnification += 1
        else:
            self.magnification -= 1

        if (self.magnification < 1):
            self.magnification = 1
        if (self.magnification > 8):
            self.magnification = 8
    
        [ev_x, ev_y] = self.camera_widget.getEventLocation(event)
        self.h_scroll_bar.setCurRatio(ev_x)
        self.v_scroll_bar.setCurRatio(ev_y)
        self.camera_widget.setMagnification(self.magnification)

        
## CameraSrollBar
#
# Wrap a scroll bar so that the camera display remains more 
# or less centered on the wheel events as we zoom in and out.
#
class CameraScrollBar():

    ## __init__
    #
    # Create a camera scroll bar object.
    #
    # @param scroll_bar A PyQt scroll bar object.
    #
    def __init__(self, scroll_bar):

        self.cur_ratio = 0.5
        self.scroll_bar = scroll_bar

        self.scroll_bar.rangeChanged.connect(self.rangeChanged)

    ## rangeChanged
    #
    # Handle scroll bar range changes.
    #
    # @param new_min The new minimum value for the scroll bar.
    # @param new_max The new maximum value for the scroll bar.
    #
    def rangeChanged(self, new_min, new_max):
        if (new_max > 0):
            self.scroll_bar.setValue(int(self.cur_ratio * float(new_max)))

    ## setCurRatio
    #
    # @param new_ratio The new ratio (or center position) for the scroll bar.
    #
    def setCurRatio(self, new_ratio):
        self.cur_ratio = new_ratio


#
# The MIT License
#
# Copyright (c) 2015 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
