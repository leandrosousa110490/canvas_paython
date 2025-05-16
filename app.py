import sys
import csv # Added for table parsing
from io import BytesIO, StringIO # Added StringIO for csv module
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QToolBar, QDockWidget, QWidget, QVBoxLayout, QLabel, QPushButton, QRadioButton,
    QGraphicsRectItem, QGraphicsEllipseItem, QToolButton, QMenu, QColorDialog, QGraphicsLineItem, QFileDialog, QGraphicsPixmapItem, QMessageBox,
    QMenuBar, QSlider, QSpinBox, QGraphicsPathItem, QGraphicsPolygonItem, QHBoxLayout, QStyleOptionGraphicsItem,
    QGraphicsItemGroup, QGraphicsSimpleTextItem # Added QGraphicsItemGroup and QGraphicsSimpleTextItem
)
from PySide6.QtGui import QAction, QIcon, QColor, QPainter, QPen, QBrush, QImage, QPixmap, QPainterPath, QPolygonF, QTransform, QUndoStack, QUndoCommand, QKeySequence # Added QKeySequence
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QBuffer # QKeySequence removed from here

# Import for background removal
from PIL import Image, ImageEnhance # Added ImageEnhance
from rembg import remove

HANDLE_SIZE = 10.0
MIN_SHAPE_SIZE = 5.0

LIGHT_THEME = {
    "name": "light",
    "window_bg": QColor("#f0f0f0"),
    "text_color": QColor("black"),
    "button_bg": QColor("#e0e0e0"),
    "button_text": QColor("black"),
    "toolbar_bg": QColor("#d0d0d0"), # Made slightly darker than #dcdcdc
    "canvas_bg": QColor("white"),
    "properties_bg": QColor("#f5f5f5"),
    "item_default_fill": QColor("#aaffaa"), # Light green
    "item_default_outline": QColor("black"),
    "selected_handle_fill": QColor("white"),
    "selected_handle_outline": QColor("black"),
    "preview_dash_color": QColor("darkgray"),
    "stylesheet": """
        QMainWindow {{ background-color: {window_bg}; color: {text_color}; }}
        QToolBar {{ background-color: {toolbar_bg}; border: 1px solid #b0b0b0; }} /* Darker border */
        QDockWidget {{ background-color: {properties_bg}; titlebar-close-icon: url(none); titlebar-normal-icon: url(none); }}
        QDockWidget::title {{ background-color: {toolbar_bg}; border: 1px solid #b0b0b0; padding: 4px; }}
        QPushButton {{ background-color: {button_bg}; color: {button_text}; border: 1px solid #b0b0b0; padding: 5px; }}
        QPushButton:hover {{ background-color: #f0f0f0; }}
        QLabel {{ color: {text_color}; }}
        QToolButton {{ background-color: {button_bg}; color: {button_text}; border: 1px solid #b0b0b0; padding: 4px; }}
        QToolButton::menu-indicator {{ image: none; }}
        QMenu {{ background-color: {toolbar_bg}; color: {text_color}; border: 1px solid #b0b0b0; }}
        QMenu::item:selected {{ background-color: #b0b0b0; }}
    """
}

DARK_THEME = {
    "name": "dark",
    "window_bg": QColor("#2e2e2e"),
    "text_color": QColor("white"),
    "button_bg": QColor("#505050"),
    "button_text": QColor("white"),
    "toolbar_bg": QColor("#383838"),
    "canvas_bg": QColor("#3a3a3a"),
    "properties_bg": QColor("#333333"),
    "item_default_fill": QColor("#306030"), # Darker green
    "item_default_outline": QColor("lightgray"),
    "selected_handle_fill": QColor("#444444"),
    "selected_handle_outline": QColor("lightgray"),
    "preview_dash_color": QColor("lightgray"),
    "stylesheet": """
        QMainWindow {{ background-color: {window_bg}; color: {text_color}; }}
        QToolBar {{ background-color: {toolbar_bg}; border: 1px solid #202020; }}
        QDockWidget {{ background-color: {properties_bg}; color: {text_color}; }}
        QDockWidget::title {{ background-color: {toolbar_bg}; border: 1px solid #202020; padding: 4px; color: {text_color};}}
        QPushButton {{ background-color: {button_bg}; color: {button_text}; border: 1px solid #202020; padding: 5px; }}
        QPushButton:hover {{ background-color: #606060; }}
        QLabel {{ color: {text_color}; }}
        QToolButton {{ background-color: {button_bg}; color: {text_color}; border: 1px solid #202020; padding: 4px; }}
        QToolButton::menu-indicator {{ image: none; }}
        QMenu {{ background-color: {toolbar_bg}; color: {text_color}; border: 1px solid #202020; }}
        QMenu::item:selected {{ background-color: #555555; }}
    """
}

# Helper function to convert QImage to PIL Image
def qimage_to_pil(qimage):
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.ReadWrite)
    # Determine format based on qimage properties, default to PNG for broad compatibility with alpha
    # qimage.save(buffer, "PNG") # Specify format
    # Let Qt choose the best format, or be more specific. PNG is good for alpha.
    if qimage.hasAlphaChannel():
        qimage.save(buffer, "PNG")
    else:
        qimage.save(buffer, "JPG") # Or PNG if preferred even without alpha
    
    pil_im = Image.open(BytesIO(buffer.data()))
    return pil_im

# Helper function to convert PIL Image to QImage
def pil_to_qimage(pil_image):
    # Ensure PIL image is in a mode that QImage can easily handle (e.g., RGBA for alpha)
    if pil_image.mode == "P": # Palette mode, convert to RGBA
        pil_image = pil_image.convert("RGBA")
    elif pil_image.mode == "RGB":
        pil_image = pil_image.convert("RGBA") # Add alpha channel for consistency
    elif pil_image.mode != "RGBA": # For other modes, ensure it's something QImage likes
        pil_image = pil_image.convert("RGBA") 

    data = pil_image.tobytes("raw", "RGBA")
    qimage = QImage(data, pil_image.size[0], pil_image.size[1], QImage.Format.Format_RGBA8888)
    return qimage.copy() # Return a copy to avoid issues with data lifetime

# --- Undo Commands ---
class AddItemCommand(QUndoCommand):
    def __init__(self, item, scene, description="Add Item"):
        super().__init__(description)
        self.item = item
        self.scene = scene
        # redo() is called implicitly by QUndoStack when command is pushed first time.
        # So item should not be added to scene before command is pushed.

    def undo(self):
        # The scene will emit selectionChanged if the removed item was selected.
        # on_scene_selection_changed in CanvasWindow should handle UI updates.
        self.scene.removeItem(self.item)
        # self.scene.update() # removeItem should handle necessary updates.
        self.setText(f"Undo {self.itemDataText()}") 

    def redo(self):
        self.scene.addItem(self.item)
        # Setting selected=True will also trigger scene.selectionChanged.
        self.item.setSelected(True)
        # self.scene.update() # addItem and setSelected should handle updates.
        self.setText(f"Redo {self.itemDataText()}") 

    def itemDataText(self):
        # Helper for more descriptive text based on item type
        if isinstance(self.item, QGraphicsRectItem): return "Rectangle"
        if isinstance(self.item, QGraphicsEllipseItem): return "Ellipse"
        if isinstance(self.item, QGraphicsLineItem): return "Line"
        if isinstance(self.item, QGraphicsPolygonItem): return "Triangle"
        if isinstance(self.item, QGraphicsPathItem): return "Pen Stroke"
        if isinstance(self.item, QGraphicsPixmapItem): return "Image"
        if isinstance(self.item, QGraphicsItemGroup): return "Table" # For pasted tables
        return "Item"

class CustomGraphicsView(QGraphicsView):
    def __init__(self, scene, parent_window):
        super().__init__(scene)
        self.parent_window = parent_window
        self.start_pos_scene = None
        self.current_preview_item_view = None
        self.is_erasing_active = False # Track if eraser is currently dragging
        self.current_drawing_path_item = None # For Pen tool
        
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # Resize specific attributes
        self.item_being_resized = None
        self.current_resize_handle_type = None
        self.resize_start_pos_scene = None
        self.original_item_rect_on_resize_start = None
        self.original_item_scale_on_resize_start = None # Added for scaling

    def mousePressEvent(self, event):
        tool = self.parent_window.current_tool

        if tool == "hand":
            super().mousePressEvent(event) # Pass directly to base for hand tool
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos_scene = self.mapToScene(event.position().toPoint())
            item_at_click = self.itemAt(event.position().toPoint())

            # Check for crop handle interaction first, as it takes precedence if active
            if self.parent_window.current_crop_item and item_at_click and hasattr(item_at_click, 'is_crop_handle'):
                # Ensure the handle belongs to the active crop_overlay_rect
                if item_at_click.parentItem() == self.parent_window.crop_overlay_rect:
                    self.item_being_resized = self.parent_window.crop_overlay_rect # We are resizing the crop overlay
                    self.current_resize_handle_type = item_at_click.handle_type # e.g., "se_crop"
                    self.resize_start_pos_scene = self.start_pos_scene
                    self.original_item_rect_on_resize_start = self.parent_window.crop_overlay_rect.rect() # Crop rect in its own coords
                    event.accept()
                    return

            if tool == "select":
                # item_at_click is already fetched
                if item_at_click and hasattr(item_at_click, 'is_resize_handle'): # Check if it's one of our item resize handles
                    # Ensure it belongs to the currently selected_item if one exists
                    if self.parent_window.selected_item and item_at_click.parentItem() == self.parent_window.selected_item:
                        self.item_being_resized = item_at_click.parentItem()
                        self.current_resize_handle_type = item_at_click.handle_type
                        self.resize_start_pos_scene = self.start_pos_scene
                        if self.item_being_resized:
                            # Store original rect and scale for resize operation
                            if isinstance(self.item_being_resized, (QGraphicsRectItem, QGraphicsEllipseItem)):
                                self.original_item_rect_on_resize_start = self.item_being_resized.rect()
                            else: # For Pixmap, Path, Polygon, Line, use boundingRect
                                self.original_item_rect_on_resize_start = self.item_being_resized.boundingRect()
                            
                            self.original_item_scale_on_resize_start = self.item_being_resized.scale()

                        else:
                            self.current_resize_handle_type = None
                            super().mousePressEvent(event) # Fallback
                            return
                        event.accept()
                        return
                    else:
                         # Clicked a resize handle for a non-selected item, or no item selected
                        super().mousePressEvent(event) # Let base class handle it (might select the item)
                        return 
                else:
                    # If not on a handle, let the base class handle selection/movement
                    super().mousePressEvent(event)
                    return
            elif tool == "hand":
                super().mousePressEvent(event) # Allow hand tool to initiate drag
                return
            elif tool == "eraser":
                self.is_erasing_active = True
                self._erase_at_point(self.start_pos_scene) # Erase at the initial press point
                event.accept()
                return
            elif tool == "pen":
                # Start a new path
                self.current_drawing_path_item = QGraphicsPathItem()
                self.scene().addItem(self.current_drawing_path_item)
                
                # Configure pen for the path item
                pen = QPen(self.parent_window.current_pen_color,
                           self.parent_window.current_pen_width,
                           Qt.PenStyle.SolidLine,
                           Qt.PenCapStyle.RoundCap,
                           Qt.PenJoinStyle.RoundJoin)
                self.current_drawing_path_item.setPen(pen)
                
                # Create the QPainterPath and move to the start point
                painter_path = QPainterPath()
                painter_path.moveTo(self.start_pos_scene)
                self.current_drawing_path_item.setPath(painter_path)
                event.accept()
                return
            # For drawing tools, start_pos_scene is already set, handled in move/release

        # Fallback for other mouse buttons or if not handled above
        # super().mousePressEvent(event)
        # We need to be careful not to call super multiple times or when not needed
        # If it's not a left click or not a tool we handle custom press for, let super handle it.
        if not (event.button() == Qt.MouseButton.LeftButton and tool in ["rectangle", "ellipse", "line", "select", "hand"]):
            super().mousePressEvent(event)


    def mouseMoveEvent(self, event):
        tool = self.parent_window.current_tool

        if tool == "hand":
            super().mouseMoveEvent(event) # Pass directly to base for hand tool
            return

        current_pos_scene = self.mapToScene(event.position().toPoint())
        theme_colors = self.parent_window.current_theme_colors

        if self.item_being_resized and self.current_resize_handle_type and (event.buttons() & Qt.MouseButton.LeftButton):
            if not self.item_being_resized or not self.item_being_resized.scene():
                self.item_being_resized = None
                self.current_resize_handle_type = None
                return

            # Calculate delta in scene coordinates, then transform to parent item's coordinates for rect manipulation
            # For crop_overlay_rect, its parent is current_crop_item. We need delta in parent's (image item) coords.
            # For regular item resize, parent is null (items are top-level), delta is in scene coords.

            # Scene delta is fine for now as handles are positioned relative to item_being_resized's rect directly.
            # The self.original_item_rect_on_resize_start is in item_being_resized's own coordinate system.
            # dx/dy needs to be in the coordinate system of self.original_item_rect_on_resize_start

            # If resizing crop_overlay_rect, its coordinates are relative to current_crop_item (the image)
            # The self.resize_start_pos_scene and current_pos_scene are in scene coords.
            # We need the delta in the coordinate system of crop_overlay_rect (which is child of current_crop_item)
            
            # Get the transform from scene to the parent of the item_being_resized (if it has one)
            # or to the item itself if it's a top-level item for its own handles.
            target_item_for_coords = self.item_being_resized
            if self.item_being_resized == self.parent_window.crop_overlay_rect:
                # crop_overlay_rect is a child of current_crop_item. Its rect is in current_crop_item's coords.
                # Handles are children of crop_overlay_rect. Their movements affect crop_overlay_rect's rect.
                # We need dx, dy in crop_overlay_rect's parent (current_crop_item) coordinate system.
                parent_of_resized = self.item_being_resized.parentItem()
                if parent_of_resized: # Should be current_crop_item
                    map_to_parent_transform = parent_of_resized.sceneTransform().inverted()[0]
                    start_pos_parent = map_to_parent_transform.map(self.resize_start_pos_scene)
                    current_pos_parent = map_to_parent_transform.map(current_pos_scene)
                    dx = current_pos_parent.x() - start_pos_parent.x()
                    dy = current_pos_parent.y() - start_pos_parent.y()
                else: # Should not happen for crop_overlay_rect
                    dx = current_pos_scene.x() - self.resize_start_pos_scene.x()
                    dy = current_pos_scene.y() - self.resize_start_pos_scene.y()
            else:
                 # For direct item resize, dx/dy in scene coords is fine as item.rect() is also scene-relative for top-level items with no parent for rect manipulation.
                 # No, item.rect() is item-local. So dx, dy must be in item-local coords.
                map_to_item_transform = self.item_being_resized.sceneTransform().inverted()[0]
                start_pos_item = map_to_item_transform.map(self.resize_start_pos_scene)
                current_pos_item = map_to_item_transform.map(current_pos_scene)
                dx = current_pos_item.x() - start_pos_item.x()
                dy = current_pos_item.y() - start_pos_item.y()

            new_rect = QRectF(self.original_item_rect_on_resize_start)

            # Apply resize logic based on handle type
            if self.current_resize_handle_type == "se": # Standard item SE resize
                original_rect_local = self.original_item_rect_on_resize_start # This is rect/boundingRect in local coords
                
                if isinstance(self.item_being_resized, (QGraphicsRectItem, QGraphicsEllipseItem)):
                    new_local_rect = QRectF(original_rect_local)
                    # dx and dy are already in the item's local coordinate system.
                    new_local_rect.setBottomRight(QPointF(new_local_rect.bottomRight().x() + dx, new_local_rect.bottomRight().y() + dy))
                    if new_local_rect.width() < MIN_SHAPE_SIZE: new_local_rect.setWidth(MIN_SHAPE_SIZE)
                    if new_local_rect.height() < MIN_SHAPE_SIZE: new_local_rect.setHeight(MIN_SHAPE_SIZE)
                    self.item_being_resized.setRect(new_local_rect.normalized())
                
                elif isinstance(self.item_being_resized, (QGraphicsPixmapItem, QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsLineItem)):
                    # Proportional scaling for these types using SE handle
                    # dx is local change in width if handle was at bottom-right of original_rect_local
                    desired_new_local_width = original_rect_local.width() + dx
                    if desired_new_local_width < MIN_SHAPE_SIZE: desired_new_local_width = MIN_SHAPE_SIZE

                    current_item_initial_scale = self.original_item_scale_on_resize_start 
                    
                    base_width_for_scaling = 0
                    if isinstance(self.item_being_resized, QGraphicsPixmapItem):
                        # For pixmaps, base width is its unscaled pixmap width.
                        base_width_for_scaling = self.item_being_resized.pixmap().width() 
                    else: 
                        # For Path, Polygon, Line: their "base width" is effectively their 
                        # bounding rect width when their scale is 1.0.
                        # original_rect_local.width() is the width at current_item_initial_scale.
                        # So, base_width = original_rect_local.width() / current_item_initial_scale
                        if current_item_initial_scale != 0:
                            base_width_for_scaling = original_rect_local.width() / current_item_initial_scale
                        else: # Item scale is 0, use original_rect_local.width as base (will result in 0 scale if width is 0)
                            base_width_for_scaling = original_rect_local.width()


                    if base_width_for_scaling > 0:
                        new_scale_value = desired_new_local_width / base_width_for_scaling
                        if new_scale_value < (MIN_SHAPE_SIZE / base_width_for_scaling) and desired_new_local_width == MIN_SHAPE_SIZE : # ensure min size is respected via scale
                             pass # new_scale_value is already minimal to achieve MIN_SHAPE_SIZE if base_width is not 0
                        elif new_scale_value * base_width_for_scaling < MIN_SHAPE_SIZE : # general check if scaling down too much
                             new_scale_value = MIN_SHAPE_SIZE / base_width_for_scaling


                        self.item_being_resized.setScale(new_scale_value)
                    # else: item has no base width or original scale was 0, cannot meaningfully scale.
            
            # --- Crop Handle Resizing Logic (item_being_resized is crop_overlay_rect) ---
            elif self.current_resize_handle_type == "nw_crop":
                new_rect.setTopLeft(QPointF(new_rect.topLeft().x() + dx, new_rect.topLeft().y() + dy))
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "n_crop":
                new_rect.setTop(new_rect.top() + dy)
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "ne_crop":
                new_rect.setTopRight(QPointF(new_rect.topRight().x() + dx, new_rect.topRight().y() + dy))
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "w_crop":
                new_rect.setLeft(new_rect.left() + dx)
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "e_crop":
                new_rect.setRight(new_rect.right() + dx)
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "sw_crop":
                new_rect.setBottomLeft(QPointF(new_rect.bottomLeft().x() + dx, new_rect.bottomLeft().y() + dy))
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "s_crop":
                new_rect.setBottom(new_rect.bottom() + dy)
                self.constrain_and_set_crop_rect(new_rect)
            elif self.current_resize_handle_type == "se_crop":
                new_rect.setBottomRight(QPointF(new_rect.bottomRight().x() + dx, new_rect.bottomRight().y() + dy))
                self.constrain_and_set_crop_rect(new_rect)
            
            # Update handles based on what was resized
            if self.item_being_resized == self.parent_window.crop_overlay_rect:
                self.parent_window._update_crop_handles()
            else: # Regular item resize
                self.parent_window._update_resize_handles_for_item(self.item_being_resized)
            event.accept()
            return
        
        # --- Drawing tools preview logic ---
        elif self.start_pos_scene and (event.buttons() & Qt.MouseButton.LeftButton) and tool in ["rectangle", "ellipse", "line", "triangle"]:
            # current_pos_scene is already available
            if self.current_preview_item_view:
                self.scene().removeItem(self.current_preview_item_view)
                self.current_preview_item_view = None
            
            preview_pen = QPen(theme_colors["preview_dash_color"]) # Use themed preview color
            preview_pen.setStyle(Qt.PenStyle.DashLine)

            bounding_rect = QRectF(self.start_pos_scene, current_pos_scene).normalized()

            if tool == "rectangle":
                self.current_preview_item_view = QGraphicsRectItem(bounding_rect)
            elif tool == "ellipse":
                self.current_preview_item_view = QGraphicsEllipseItem(bounding_rect)
            elif tool == "line":
                self.current_preview_item_view = QGraphicsLineItem(self.start_pos_scene.x(), self.start_pos_scene.y(),
                                                                   current_pos_scene.x(), current_pos_scene.y())
            elif tool == "triangle":
                p1 = QPointF(bounding_rect.center().x(), bounding_rect.top())
                p2 = QPointF(bounding_rect.left(), bounding_rect.bottom())
                p3 = QPointF(bounding_rect.right(), bounding_rect.bottom())
                polygon = QPolygonF([p1, p2, p3])
                self.current_preview_item_view = QGraphicsPolygonItem(polygon)
            
            if self.current_preview_item_view:
                self.current_preview_item_view.setPen(preview_pen)
                # For shapes that can have a fill, make preview fill transparent
                if tool in ["rectangle", "ellipse", "triangle"]:
                     self.current_preview_item_view.setBrush(Qt.BrushStyle.NoBrush)
                self.scene().addItem(self.current_preview_item_view)
            return # Handled drawing move
        elif tool == "eraser" and self.is_erasing_active and (event.buttons() & Qt.MouseButton.LeftButton):
            self._erase_at_point(current_pos_scene)
            event.accept()
            return
        elif tool == "pen" and self.current_drawing_path_item and (event.buttons() & Qt.MouseButton.LeftButton):
            current_path = self.current_drawing_path_item.path()
            current_path.lineTo(current_pos_scene)
            self.current_drawing_path_item.setPath(current_path)
            event.accept()
            return
        
        # Fallback to super for other moves (like item movement by select tool, hand tool panning)
        super().mouseMoveEvent(event)

    def constrain_and_set_crop_rect(self, new_rect_proposed):
        # Helper function for crop rectangle updates
        if not (self.item_being_resized == self.parent_window.crop_overlay_rect and self.parent_window.current_crop_item):
            return

        image_bounds = self.parent_window.current_crop_item.boundingRect()
        constrained_rect = QRectF(new_rect_proposed) # Work on a copy

        # Constrain top-left
        if constrained_rect.left() < image_bounds.left(): constrained_rect.setLeft(image_bounds.left())
        if constrained_rect.top() < image_bounds.top(): constrained_rect.setTop(image_bounds.top())
        # Constrain bottom-right
        if constrained_rect.right() > image_bounds.right(): constrained_rect.setRight(image_bounds.right())
        if constrained_rect.bottom() > image_bounds.bottom(): constrained_rect.setBottom(image_bounds.bottom())

        # Enforce minimum size after constraining
        if constrained_rect.width() < MIN_SHAPE_SIZE:
            # Try to adjust from the side that wasn't explicitly against the boundary, if possible
            if constrained_rect.left() == image_bounds.left() and constrained_rect.right() != image_bounds.right():
                 constrained_rect.setRight(constrained_rect.left() + MIN_SHAPE_SIZE)
            else: # Default to expanding/setting width from left or right if it was against boundary
                 constrained_rect.setWidth(MIN_SHAPE_SIZE)
        if constrained_rect.height() < MIN_SHAPE_SIZE:
            if constrained_rect.top() == image_bounds.top() and constrained_rect.bottom() != image_bounds.bottom():
                constrained_rect.setBottom(constrained_rect.top() + MIN_SHAPE_SIZE)
            else:
                constrained_rect.setHeight(MIN_SHAPE_SIZE)
        
        # Final check: ensure it's still within bounds after min size adjustment if min_size pushed it out
        if constrained_rect.right() > image_bounds.right(): constrained_rect.setRight(image_bounds.right())
        if constrained_rect.bottom() > image_bounds.bottom(): constrained_rect.setBottom(image_bounds.bottom())
        if constrained_rect.left() < image_bounds.left(): constrained_rect.setLeft(image_bounds.left())
        if constrained_rect.top() < image_bounds.top(): constrained_rect.setTop(image_bounds.top())

        self.item_being_resized.setRect(constrained_rect.normalized())

    def mouseReleaseEvent(self, event):
        tool = self.parent_window.current_tool
        current_pos_scene = self.mapToScene(event.position().toPoint()) # Defined for general use

        item_that_was_resized = None
        if self.item_being_resized and event.button() == Qt.MouseButton.LeftButton:
            print(f"Resizing finished for: {self.item_being_resized}, handle: {self.current_resize_handle_type}")
            item_that_was_resized = self.item_being_resized # Store before clearing
            if self.item_being_resized == self.parent_window.crop_overlay_rect:
                self.parent_window._update_crop_handles()
            else:
                 if self.parent_window.selected_item:
                     self.parent_window._update_resize_handles_for_item(self.parent_window.selected_item)
            
            self.item_being_resized = None
            self.current_resize_handle_type = None
            self.resize_start_pos_scene = None
            self.original_item_rect_on_resize_start = None
            self.original_item_scale_on_resize_start = None
            event.accept()

            # After mouse resize, update properties panel for the item that was resized, if it's a pixmap
            if item_that_was_resized and isinstance(item_that_was_resized, QGraphicsPixmapItem) and item_that_was_resized == self.parent_window.selected_item:
                self.parent_window._update_image_size_spinboxes(item_that_was_resized)
            return

        # --- Drawing tools finalization logic ---
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos_scene and tool in ["rectangle", "ellipse", "line", "triangle"]:
            if self.current_preview_item_view:
                self.scene().removeItem(self.current_preview_item_view)
                self.current_preview_item_view = None

            final_item = None
            outline_color = self.parent_window.current_theme_colors["item_default_outline"]
            fill_color = self.parent_window.current_theme_colors["item_default_fill"]
            pen = QPen(outline_color)
            brush = QBrush(fill_color)

            final_bounding_rect = QRectF(self.start_pos_scene, current_pos_scene).normalized()

            if tool == "rectangle" or tool == "ellipse" or tool == "triangle":
                # Ensure minimum size for shapes based on bounding box
                if final_bounding_rect.width() < MIN_SHAPE_SIZE or final_bounding_rect.height() < MIN_SHAPE_SIZE:
                    self.start_pos_scene = None # Reset to prevent accidental small shape
                    return

                if tool == "rectangle":
                    final_item = QGraphicsRectItem(final_bounding_rect)
                elif tool == "ellipse":
                    final_item = QGraphicsEllipseItem(final_bounding_rect)
                elif tool == "triangle":
                    p1 = QPointF(final_bounding_rect.center().x(), final_bounding_rect.top())
                    p2 = QPointF(final_bounding_rect.left(), final_bounding_rect.bottom())
                    p3 = QPointF(final_bounding_rect.right(), final_bounding_rect.bottom())
                    polygon = QPolygonF([p1, p2, p3])
                    final_item = QGraphicsPolygonItem(polygon)
                    if final_item: final_item.shape_type = "triangle" # Custom attribute
                
                if final_item and tool in ["rectangle", "ellipse", "triangle"]:
                    final_item.setBrush(brush)

            elif tool == "line":
                # Check for minimal length for a line, if desired (e.g., avoid zero-length lines)
                if (self.start_pos_scene - current_pos_scene).manhattanLength() > MIN_SHAPE_SIZE / 2:
                    final_item = QGraphicsLineItem(self.start_pos_scene.x(), self.start_pos_scene.y(),
                                                   current_pos_scene.x(), current_pos_scene.y())
            
            if final_item:
                final_item.setPen(pen)
                final_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
                final_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
                # self.scene().addItem(final_item) # Old direct add
                command = AddItemCommand(final_item, self.scene(), f"Add {AddItemCommand(final_item, self.scene()).itemDataText()}")
                self.parent_window.undo_stack.push(command)
                # The redo() of the command will select it.

            self.start_pos_scene = None 
            return # Handled drawing release
        elif tool == "eraser" and event.button() == Qt.MouseButton.LeftButton:
            if self.is_erasing_active:
                self._erase_at_point(self.mapToScene(event.position().toPoint())) # Final erase point
                self.is_erasing_active = False
                event.accept()
            return
        elif tool == "pen" and self.current_drawing_path_item and event.button() == Qt.MouseButton.LeftButton:
            # Finalize the path, make it selectable/movable
            self.current_drawing_path_item.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable)
            self.current_drawing_path_item.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsMovable)
            # Add custom attributes if needed, e.g., item_type
            self.current_drawing_path_item.item_type = "pen_stroke"
            # self.scene().addItem(self.current_drawing_path_item) # No, command will do it
            command = AddItemCommand(self.current_drawing_path_item, self.scene(), "Add Pen Stroke")
            self.parent_window.undo_stack.push(command)
            self.current_drawing_path_item = None 
            event.accept()
            return

        # Fallback to super for other releases
        super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        old_pos = self.mapToScene(event.position().toPoint())
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
        self.scale(zoom_factor, zoom_factor)
        new_pos = self.mapToScene(event.position().toPoint())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def contextMenuEvent(self, event):
        # Create a context menu
        menu = QMenu(self)
        scene_pos = self.mapToScene(event.pos())

        # Check if there is text on the clipboard
        clipboard = QApplication.clipboard()
        has_text_on_clipboard = clipboard.mimeData().hasText()

        paste_table_action = QAction("Paste Table", self)
        paste_table_action.setEnabled(has_text_on_clipboard)
        paste_table_action.triggered.connect(lambda: self.parent_window.paste_table_from_clipboard(scene_pos))
        menu.addAction(paste_table_action)

        # Show the context menu at the event position
        menu.exec(event.globalPos())
        # super().contextMenuEvent(event) # Optional: call if you want base class behavior too

    def _erase_at_point(self, scene_pos):
        brush_size = self.parent_window.eraser_brush_size
        eraser_rect_scene = QRectF(
            scene_pos.x() - brush_size / 2,
            scene_pos.y() - brush_size / 2,
            brush_size,
            brush_size
        )

        items_to_erase = self.scene().items(eraser_rect_scene, Qt.IntersectsItemShape)

        for item in items_to_erase:
            if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem)) and not hasattr(item, 'is_rasterized_for_erase'):
                # Convert vector item to QGraphicsPixmapItem
                # 1. Create a QPixmap from the item
                item_brect = item.boundingRect() # Get bounding rect in its own coordinate system
                
                # Create a QImage to render on. Make it slightly larger if item has pen width to avoid clipping.
                # For simplicity, using boundingRect which includes pen width.
                render_image = QImage(item_brect.size().toSize(), QImage.Format.Format_ARGB32_Premultiplied)
                render_image.fill(Qt.GlobalColor.transparent) # Start with a transparent image
                
                painter = QPainter(render_image)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Important: Render the item at (0,0) in the image.
                # The item's sceneTransform() handles its position and scale.
                # We need to temporarily move item to 0,0 or adjust painter.
                
                # Option A: Render with item's current transformations applied directly.
                # This might be complex if item has rotation/shear.

                # Option B: Render the item as if its top-left of boundingRect is at (0,0) of the image
                painter.translate(-item_brect.topLeft()) # Adjust painter to draw item at origin of its BR
                
                # Set painter state from item (pen, brush)
                # This is crucial and needs to be comprehensive.
                if hasattr(item, 'pen'): painter.setPen(item.pen())
                if hasattr(item, 'brush') and not isinstance(item, QGraphicsLineItem): # Lines don't have brush
                    painter.setBrush(item.brush())

                # Actual drawing call depends on item type
                if isinstance(item, QGraphicsRectItem):
                    painter.drawRect(item.rect()) # item.rect() is in item's local coords
                elif isinstance(item, QGraphicsEllipseItem):
                    painter.drawEllipse(item.rect())
                elif isinstance(item, QGraphicsLineItem):
                    painter.drawLine(item.line())
                painter.end()

                new_pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(render_image))
                new_pixmap_item.setPos(item.scenePos()) # Position the new pixmap item where the old vector item was
                new_pixmap_item.setTransformOriginPoint(item.transformOriginPoint()) # Preserve transform origin
                new_pixmap_item.setRotation(item.rotation())
                new_pixmap_item.setScale(item.scale())
                
                # Copy flags
                new_pixmap_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, item.flags() & QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
                new_pixmap_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, item.flags() & QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
                
                new_pixmap_item.is_rasterized_for_erase = True
                # Store original vector data if needed for "undo rasterization" (future)
                # new_pixmap_item.original_vector_data = item 
                
                self.scene().removeItem(item)
                self.scene().addItem(new_pixmap_item)
                # The 'item' variable now refers to the new QGraphicsPixmapItem for subsequent erasing
                # We should re-assign 'item' to new_pixmap_item for the current erase pass
                print(f"Converted vector item to pixmap for erasing.")
                item = new_pixmap_item 
                # Important: if item was selected, the selection is lost. Re-selecting new_pixmap_item might be needed.
                # This also means resize handles will be lost. This needs further thought.
                # For now, focus on erasing part.

            if isinstance(item, QGraphicsPixmapItem):
                # Ensure the item has a modifiable QImage
                if not hasattr(item, 'modifiable_qimage') or item.modifiable_qimage is None:
                    item.modifiable_qimage = item.pixmap().toImage().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                
                # Map eraser_rect_scene (which is in scene coordinates) to item's local coordinates
                # item.mapFromScene() returns a QPolygonF. We need a QRectF for painter.drawRect.
                # So, map the four corners of the eraser_rect_scene and construct a QPainterPath or QPolygonF in item coords.
                
                transform = item.sceneTransform().inverted()[0] # Matrix to map from scene to item
                # Create an empty path, add the rectangle, then map it
                temp_path = QPainterPath()
                temp_path.addRect(eraser_rect_scene)
                item_eraser_path = transform.map(temp_path)

                if not hasattr(item, 'pil_for_display'): # Should exist if it's an image we loaded
                    print("Error: Image item does not have pil_for_display for erasing.")
                    continue

                # Ensure the item has a modifiable QImage for erasing
                if not hasattr(item, 'modifiable_qimage') or item.modifiable_qimage is None:
                    # Source from pil_for_display which has all current effects
                    item.modifiable_qimage = pil_to_qimage(item.pil_for_display).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                
                if item.modifiable_qimage.isNull():
                    print("Error: modifiable_qimage is null")
                    continue

                img_painter = QPainter(item.modifiable_qimage)
                img_painter.setCompositionMode(QPainter.CompositionMode_Clear)
                # img_painter.fillRect(item_eraser_rect, Qt.GlobalColor.transparent) # fillRect needs QRect or QRectF
                img_painter.fillPath(item_eraser_path, Qt.GlobalColor.transparent) # Using fillPath for more accuracy
                img_painter.end()
                
                item.setPixmap(QPixmap.fromImage(item.modifiable_qimage))
                # Update pil_for_display to reflect the erased state
                item.pil_for_display = qimage_to_pil(item.modifiable_qimage)


class CanvasWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qt Canvas Application")
        self.setGeometry(100, 100, 1200, 800)

        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(QColor("white"))
        self.view = CustomGraphicsView(self.scene, self)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setCentralWidget(self.view)

        self.current_tool = "select"
        self.selected_item = None
        self.active_resize_handles = [] 
        self.zoom_factor = 1.0 
        self.eraser_brush_size = 10.0 
        self.current_crop_item = None      
        self.crop_overlay_rect = None    
        self.active_crop_handles = []    
        self.keep_image_aspect_ratio_on_resize = True 

        # --- Undo Stack ---
        self.undo_stack = QUndoStack(self)

        self.themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        self.current_theme_name = "dark" # Default theme set to dark
        self.current_theme_colors = self.themes[self.current_theme_name]
        self.custom_canvas_bg_color = None # To store user-picked canvas bg
        self.current_pen_color = self.current_theme_colors["item_default_outline"] # Default pen color
        self.current_pen_width = 2.0 # Default pen width

        self.toolbar = QToolBar("Main Toolbar")
        self.addToolBar(self.toolbar)

        # --- Tool Actions (Select & Hand directly on toolbar) ---
        select_action = QAction("Select", self)
        select_action.setCheckable(True)
        select_action.triggered.connect(lambda: self.set_tool("select"))
        self.toolbar.addAction(select_action)

        hand_action = QAction("Hand", self)
        hand_action.setCheckable(True)
        hand_action.triggered.connect(lambda: self.set_tool("hand"))
        self.toolbar.addAction(hand_action)
        
        self.main_tool_actions_group = [select_action, hand_action] # For direct toolbar tools

        self.toolbar.addSeparator()

        # Eraser Action (will be grouped with select/hand eventually)
        eraser_action = QAction("Eraser", self)
        eraser_action.setCheckable(True)
        eraser_action.triggered.connect(lambda: self.set_tool("eraser"))
        self.toolbar.addAction(eraser_action)
        self.main_tool_actions_group.append(eraser_action) # Add to group for radio-button like behavior

        self.toolbar.addSeparator()

        # --- Shape Tools Dropdown ---
        self.shape_tool_button = QToolButton(self)
        self.shape_tool_button.setText("Shapes") # Default text
        self.shape_tool_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.shape_menu = QMenu(self.shape_tool_button)
        
        rect_shape_action = QAction("Rectangle", self)
        rect_shape_action.triggered.connect(lambda: self.set_tool("rectangle"))
        self.shape_menu.addAction(rect_shape_action)

        ellipse_shape_action = QAction("Ellipse", self)
        ellipse_shape_action.triggered.connect(lambda: self.set_tool("ellipse"))
        self.shape_menu.addAction(ellipse_shape_action)

        line_shape_action = QAction("Line", self)
        line_shape_action.triggered.connect(lambda: self.set_tool("line"))
        self.shape_menu.addAction(line_shape_action)

        pen_tool_action = QAction("Pen", self)
        pen_tool_action.triggered.connect(lambda: self.set_tool("pen"))
        self.shape_menu.addAction(pen_tool_action)

        triangle_action = QAction("Triangle", self)
        triangle_action.triggered.connect(lambda: self.set_tool("triangle"))
        self.shape_menu.addAction(triangle_action)
        # Add more shape actions here later

        self.shape_tool_button.setMenu(self.shape_menu)
        self.toolbar.addWidget(self.shape_tool_button)
        
        self.current_shape_tool_action = rect_shape_action # Default shape tool
        self.update_shape_tool_button_text()

        self.toolbar.addSeparator()

        # Add Image Action
        add_image_action = QAction("Add Image", self)
        add_image_action.triggered.connect(self.add_image_prompt)
        self.toolbar.addAction(add_image_action)
        self.toolbar.addSeparator()

        # Delete Action
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.delete_selected_item)
        delete_action.setShortcut(Qt.Key.Key_Delete) # Bind Delete key
        self.toolbar.addAction(delete_action)
        self.toolbar.addSeparator()

        # --- Zoom Actions ---
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.triggered.connect(self.zoom_in)
        self.toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.triggered.connect(self.zoom_out)
        self.toolbar.addAction(zoom_out_action)

        self.toolbar.addSeparator() # Separator before new canvas bg button

        change_canvas_bg_action = QAction("Canvas Color", self)
        change_canvas_bg_action.triggered.connect(self.change_canvas_background_color)
        self.toolbar.addAction(change_canvas_bg_action)

        # --- Menu Bar ---
        menubar = self.menuBar()
        view_menu = menubar.addMenu("View")

        light_mode_action = QAction("Light Mode", self)
        light_mode_action.triggered.connect(lambda: self.apply_theme("light"))
        view_menu.addAction(light_mode_action)

        dark_mode_action = QAction("Dark Mode", self)
        dark_mode_action.triggered.connect(lambda: self.apply_theme("dark"))
        view_menu.addAction(dark_mode_action)
        
        view_menu.addSeparator()
        view_menu.addAction(change_canvas_bg_action) # Also add to menu for discoverability

        # --- Arrange Menu (New) ---
        arrange_menu = menubar.addMenu("Arrange")

        bring_to_front_action = QAction("Bring to Front", self)
        bring_to_front_action.triggered.connect(self.bring_selected_to_front)
        arrange_menu.addAction(bring_to_front_action)
        # self.toolbar.addAction(bring_to_front_action) # Add to toolbar later if desired

        send_to_back_action = QAction("Send to Back", self)
        send_to_back_action.triggered.connect(self.send_selected_to_back)
        arrange_menu.addAction(send_to_back_action)
        # self.toolbar.addAction(send_to_back_action)

        bring_forward_action = QAction("Bring Forward", self)
        bring_forward_action.triggered.connect(self.bring_selected_forward)
        arrange_menu.addAction(bring_forward_action)
        # self.toolbar.addAction(bring_forward_action)

        send_backward_action = QAction("Send Backward", self)
        send_backward_action.triggered.connect(self.send_selected_backward)
        arrange_menu.addAction(send_backward_action)
        # self.toolbar.addAction(send_backward_action)
        
        # Add a separator in toolbar before arrange actions if adding them there
        # self.toolbar.addSeparator() 
        # Example: Add "Bring to Front" and "Send to Back" to toolbar for quick access
        self.toolbar.addAction(bring_to_front_action)
        self.toolbar.addAction(send_to_back_action)

        # --- File Menu (New or Existing) ---
        # Check if File menu exists, if not create it
        file_menu = None
        for menu in menubar.findChildren(QMenu):
            if menu.title() == "File":
                file_menu = menu
                break
        if not file_menu:
            file_menu = menubar.addMenu("File")

        save_image_as_action = QAction("Save Image As...", self)
        save_image_as_action.triggered.connect(self.save_selected_image_as)
        file_menu.addAction(save_image_as_action)

        # --- Edit Menu (for Undo/Redo) ---
        edit_menu = menubar.addMenu("Edit")
        undo_action = self.undo_stack.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)

        # Add Undo/Redo to toolbar for quick access
        self.toolbar.addSeparator()
        self.toolbar.addAction(undo_action)
        self.toolbar.addAction(redo_action)

        # --- Properties Panel ---
        self.properties_dock = QDockWidget("Properties", self)
        self.properties_widget = QWidget()
        self.properties_layout = QVBoxLayout()
        self.properties_widget.setLayout(self.properties_layout)
        self.prop_label = QLabel("Select an item to see properties.")
        self.properties_layout.addWidget(self.prop_label)

        self.fill_color_button = QPushButton("Change Fill Color")
        self.fill_color_button.clicked.connect(self.change_selected_item_fill_color)
        self.properties_layout.addWidget(self.fill_color_button)
        self.current_fill_color_label = QLabel("Fill: N/A")
        self.properties_layout.addWidget(self.current_fill_color_label)

        self.outline_color_button = QPushButton("Change Outline Color")
        self.outline_color_button.clicked.connect(self.change_selected_item_outline_color)
        self.properties_layout.addWidget(self.outline_color_button)
        self.current_outline_color_label = QLabel("Outline: N/A")
        self.properties_layout.addWidget(self.current_outline_color_label)

        # Remove Background Button (for images)
        self.remove_bg_button = QPushButton("Remove Background")
        self.remove_bg_button.clicked.connect(self.remove_selected_image_background)
        self.properties_layout.addWidget(self.remove_bg_button)
        self.remove_bg_button.setVisible(False)

        # Brightness Controls (for images)
        self.brightness_label = QLabel("Brightness:")
        self.properties_layout.addWidget(self.brightness_label)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0) # 0% brightness
        self.brightness_slider.setMaximum(200) # 200% brightness
        self.brightness_slider.setValue(100) # Default 100% (no change)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_slider.setTickInterval(25)
        self.brightness_slider.valueChanged.connect(self.on_brightness_slider_changed)
        self.properties_layout.addWidget(self.brightness_slider)
        self.brightness_value_label = QLabel("100%")
        self.properties_layout.addWidget(self.brightness_value_label)

        # Crop Mode Buttons (for images)
        self.start_crop_button = QPushButton("Crop Image")
        self.start_crop_button.clicked.connect(self.enter_crop_mode)
        self.properties_layout.addWidget(self.start_crop_button)

        self.apply_crop_button = QPushButton("Apply Crop")
        self.apply_crop_button.clicked.connect(lambda: self.exit_crop_mode(apply_changes=True))
        self.properties_layout.addWidget(self.apply_crop_button)

        self.cancel_crop_button = QPushButton("Cancel Crop")
        self.cancel_crop_button.clicked.connect(lambda: self.exit_crop_mode(apply_changes=False))
        self.properties_layout.addWidget(self.cancel_crop_button)

        # Rotation Controls (for images)
        self.rotation_label = QLabel("Rotation:")
        self.properties_layout.addWidget(self.rotation_label)
        self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_slider.setMinimum(0)
        self.rotation_slider.setMaximum(359) # Degrees
        self.rotation_slider.setValue(0)
        self.rotation_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rotation_slider.setTickInterval(45)
        self.rotation_slider.valueChanged.connect(self.on_rotation_slider_changed)
        self.properties_layout.addWidget(self.rotation_slider)
        self.rotation_value_label = QLabel("0°")
        self.properties_layout.addWidget(self.rotation_value_label)

        # --- Image Size Controls (New) ---
        self.image_size_label = QLabel("Current Size:") # Overall label
        self.properties_layout.addWidget(self.image_size_label)
        
        self.image_width_label = QLabel("W:")
        self.image_width_spinbox = QSpinBox()
        self.image_width_spinbox.setRange(1, 10000) # Min 1px, Max 10000px
        # self.image_width_spinbox.valueChanged.connect(self.on_image_width_changed)
        self.image_width_spinbox.editingFinished.connect(self.on_image_width_editing_finished)
        
        self.image_height_label = QLabel("H:")
        self.image_height_spinbox = QSpinBox()
        self.image_height_spinbox.setRange(1, 10000)
        # self.image_height_spinbox.valueChanged.connect(self.on_image_height_changed)
        self.image_height_spinbox.editingFinished.connect(self.on_image_height_editing_finished)

        # Layout for width and height side-by-side
        size_control_layout = QHBoxLayout() 
        size_control_layout.addWidget(self.image_width_label)
        size_control_layout.addWidget(self.image_width_spinbox)
        size_control_layout.addSpacing(10) 
        size_control_layout.addWidget(self.image_height_label)
        size_control_layout.addWidget(self.image_height_spinbox)
        size_control_layout.addStretch() 
        self.properties_layout.addLayout(size_control_layout)

        # --- Save Image Button (Moved/New) ---
        self.save_image_button = QPushButton("Save Image As...")
        self.save_image_button.clicked.connect(self.save_selected_image_as)
        self.properties_layout.addWidget(self.save_image_button)

        # Pen Tool Properties (visible when pen tool is active)
        self.pen_color_label = QLabel("Pen Color:")
        self.properties_layout.addWidget(self.pen_color_label)
        self.change_pen_color_button = QPushButton("Change Pen Color")
        self.change_pen_color_button.clicked.connect(self.change_pen_color)
        self.properties_layout.addWidget(self.change_pen_color_button)
        self.current_pen_color_preview = QLabel("●") # Placeholder, will be styled
        self.properties_layout.addWidget(self.current_pen_color_preview)

        self.pen_width_label = QLabel("Pen Width:")
        self.properties_layout.addWidget(self.pen_width_label)
        self.pen_width_spinbox = QSpinBox()
        self.pen_width_spinbox.setMinimum(1)
        self.pen_width_spinbox.setMaximum(50)
        self.pen_width_spinbox.setValue(int(self.current_pen_width))
        self.pen_width_spinbox.valueChanged.connect(self.on_pen_width_changed)
        self.properties_layout.addWidget(self.pen_width_spinbox)

        self.brightness_label.setVisible(False)
        self.brightness_slider.setVisible(False)
        self.brightness_value_label.setVisible(False)
        self.start_crop_button.setVisible(False)
        self.apply_crop_button.setVisible(False)
        self.cancel_crop_button.setVisible(False)
        self.rotation_label.setVisible(False) # Hide by default
        self.rotation_slider.setVisible(False)
        self.rotation_value_label.setVisible(False)
        self.pen_color_label.setVisible(False)
        self.change_pen_color_button.setVisible(False)
        self.current_pen_color_preview.setVisible(False)
        self.pen_width_label.setVisible(False)
        self.pen_width_spinbox.setVisible(False)
        
        self.properties_layout.addStretch() # Pushes controls to the top
        self.properties_dock.setWidget(self.properties_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_dock)

        self.scene.selectionChanged.connect(self.on_scene_selection_changed)
        self.set_tool("select") # Initialize tool
        self._update_properties_panel_for_selection() # Initial state
        self.apply_theme(self.current_theme_name) # Apply initial theme

    def on_scene_selection_changed(self):
        try:
            # A very basic check. If self.scene is None, we can't proceed.
            if not hasattr(self, 'scene') or self.scene is None:
                print("on_scene_selection_changed: self.scene is None or not available.")
                return

            selected_items = self.scene.selectedItems() 
            self._remove_resize_handles() 

            old_selected_item = self.selected_item 

            if selected_items:
                new_selection = selected_items[0]
                if self.selected_item != new_selection: # Selection truly changed
                    self.selected_item = new_selection
                # Always ensure handles are (re)created for the current single selection
                if isinstance(self.selected_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsItemGroup)):
                    self._create_resize_handles_for_item(self.selected_item)
                print(f"Selected: {self.selected_item}")
            else:
                self.selected_item = None
                print("Selection cleared")

            self._update_properties_panel_for_selection()

            if self.current_crop_item and self.current_crop_item != self.selected_item:
                 if old_selected_item == self.current_crop_item:
                     print("Selection changed away from item in crop mode. Cancelling crop.")
                     self.exit_crop_mode(apply_changes=False)

        except RuntimeError as e:
            # Check for common messages indicating a deleted C++ object
            error_msg = str(e).lower()
            if "already deleted" in error_msg or "cannot call method" in error_msg or "null object" in error_msg:
                print(f"on_scene_selection_changed: Caught RuntimeError (C++ object likely deleted): {e}")
                # Attempt graceful cleanup or just prevent crash
                if hasattr(self, 'selected_item'): self.selected_item = None
                self._remove_resize_handles() # Try to clean handles
                if hasattr(self, 'prop_label') and self.prop_label: # Ensure prop_label exists
                    try:
                        self.prop_label.setText("Selected: None (Error)")
                    except RuntimeError: # prop_label might also be gone
                        pass 
                return
            else:
                raise # Re-raise other RuntimeErrors

    def update_shape_tool_button_text(self):
        if self.current_tool in ["rectangle", "ellipse", "line", "pen", "triangle"] and self.current_shape_tool_action:
            self.shape_tool_button.setText(self.current_shape_tool_action.text())
        else:
            # Default or if a non-shape tool is active but we want to show last shape
            self.shape_tool_button.setText(self.current_shape_tool_action.text()) 

    def set_tool(self, tool_name):
        # Temporarily disconnect pen width spinbox to prevent unintended updates during tool switch
        if hasattr(self, 'pen_width_spinbox'): # Check if it exists
            try: self.pen_width_spinbox.valueChanged.disconnect(self.on_pen_width_changed) 
            except RuntimeError: pass # If not connected, fine

        previous_tool = self.current_tool
        self.current_tool = tool_name
        print(f"Tool changed to: {self.current_tool}")

        if tool_name == "pen" and previous_tool != "pen": # Only prompt if switching TO pen tool
            # Prompt for color when Pen tool is selected
            new_color = QColorDialog.getColor(self.current_pen_color, self, "Choose Pen Color",
                                              options=QColorDialog.ColorDialogOption.DontUseNativeDialog)
            if new_color.isValid():
                self.current_pen_color = new_color
            # If user cancels, current_pen_color remains as it was

        # Uncheck main tools if a shape tool is selected from dropdown
        if tool_name in ["rectangle", "ellipse", "line", "pen", "triangle"]:
            for action in self.main_tool_actions_group:
                action.setChecked(False)
            # Update current_shape_tool_action based on tool_name
            if tool_name == "rectangle": self.current_shape_tool_action = self.shape_menu.actions()[0]
            elif tool_name == "ellipse": self.current_shape_tool_action = self.shape_menu.actions()[1]
            elif tool_name == "line": self.current_shape_tool_action = self.shape_menu.actions()[2]
            elif tool_name == "pen": self.current_shape_tool_action = self.shape_menu.actions()[3]
            elif tool_name == "triangle": self.current_shape_tool_action = self.shape_menu.actions()[4] # Assuming Triangle is 5th
            self.update_shape_tool_button_text()
            self.view.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.view.setInteractive(False) # Drawing tools manage interaction
            self.view.setCursor(Qt.CursorShape.CrossCursor) # Standard for drawing
        else: # Select, Hand, or Eraser tool
            for action in self.main_tool_actions_group:
                if action.text().lower().startswith(tool_name.lower()): # Match tool_name (e.g. "select", "hand", "eraser")
                    action.setChecked(True)
                else:
                    action.setChecked(False)
            self.update_shape_tool_button_text() # Keep showing last selected/default shape

            if self.current_tool == "select":
                self.view.setInteractive(True) # Must be interactive for item selection/movement
                self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag) # Or NoDrag if items handle their own move
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.current_tool == "hand":
                self.view.setInteractive(False) # Crucial: View handles panning, not items
                self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.view.setCursor(Qt.CursorShape.OpenHandCursor)
                self.view.setFocus(Qt.FocusReason.OtherFocusReason) # Explicitly set focus
            elif self.current_tool == "eraser":
                self.view.setInteractive(False)
                self.view.setDragMode(QGraphicsView.DragMode.NoDrag) 
        
        # Clear selection if switching away from select tool with an item selected (optional)
        if tool_name != "select" and self.selected_item:
            self.selected_item.setSelected(False) # This will trigger on_scene_selection_changed

        # Reconnect pen width spinbox if it was disconnected
        if hasattr(self, 'pen_width_spinbox') and self.current_tool != "pen": # Reconnect if not pen tool
            try: self.pen_width_spinbox.valueChanged.connect(self.on_pen_width_changed) 
            except RuntimeError: pass # May already be connected if tool switch was to pen then to something else fast

    def _remove_resize_handles(self):
        for handle in self.active_resize_handles:
            if handle.scene(): # Check if it's still in a scene
                self.scene.removeItem(handle)
        self.active_resize_handles.clear()

    def _create_resize_handles_for_item(self, parent_item):
        self._remove_resize_handles() 
        theme_colors = self.current_theme_colors

        item_rect_for_handles = None
        if isinstance(parent_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem)):
            item_rect_for_handles = parent_item.boundingRect()
            # Basic check for validity, though boundingRect should generally be valid if item is visible
            if item_rect_for_handles.isEmpty() and not (isinstance(parent_item, QGraphicsLineItem) and parent_item.line().length() == 0): # Allow zero-length line if just drawn
                 print(f"Cannot create handles for item {parent_item} with empty bounding rect.")
                 return 
        else:
            return # No handles for other types

        # SE handle (bottom-right of the bounding rect in item's local coords)
        se_pos_x = item_rect_for_handles.right() - HANDLE_SIZE / 2
        se_pos_y = item_rect_for_handles.bottom() - HANDLE_SIZE / 2
        
        se_handle = QGraphicsRectItem(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent_item) 
        se_handle.setPos(QPointF(se_pos_x, se_pos_y)) 
        se_handle.setBrush(theme_colors["selected_handle_fill"])
        se_handle.setPen(QPen(theme_colors["selected_handle_outline"]))
        se_handle.is_resize_handle = True
        se_handle.handle_type = "se"
        self.active_resize_handles.append(se_handle)

    def _update_resize_handles_for_item(self, parent_item):
        if not self.active_resize_handles or not parent_item: 
            # If no parent_item, but handles exist, they are orphaned, remove them.
            if not parent_item and self.active_resize_handles:
                self._remove_resize_handles()
            return
        
        item_rect_for_handles = None
        if isinstance(parent_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPixmapItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem)):
            item_rect_for_handles = parent_item.boundingRect()
            if item_rect_for_handles.isEmpty() and not (isinstance(parent_item, QGraphicsLineItem) and parent_item.line().length() == 0):
                self._remove_resize_handles() # Remove handles if item's rect becomes invalid
                return
        else:
            self._remove_resize_handles() 
            return
        
        for handle in self.active_resize_handles:
            if handle.handle_type == "se":
                se_pos_x = item_rect_for_handles.right() - HANDLE_SIZE / 2
                se_pos_y = item_rect_for_handles.bottom() - HANDLE_SIZE / 2
                handle.setPos(QPointF(se_pos_x, se_pos_y))
                handle.setBrush(self.current_theme_colors["selected_handle_fill"])
                handle.setPen(QPen(self.current_theme_colors["selected_handle_outline"]))

    def _update_properties_panel_for_selection(self):
        # Default to all conditional widgets hidden
        self.fill_color_button.setVisible(False)
        self.current_fill_color_label.setVisible(False)
        self.outline_color_button.setVisible(False)
        self.current_outline_color_label.setVisible(False)
        self.remove_bg_button.setVisible(False)
        self.brightness_label.setVisible(False)
        self.brightness_slider.setVisible(False)
        self.brightness_value_label.setVisible(False)
        self.start_crop_button.setVisible(False)
        self.apply_crop_button.setVisible(False)
        self.cancel_crop_button.setVisible(False)
        self.rotation_label.setVisible(False) 
        self.rotation_slider.setVisible(False)
        self.rotation_value_label.setVisible(False)
        self.pen_color_label.setVisible(False)
        self.change_pen_color_button.setVisible(False)
        self.current_pen_color_preview.setVisible(False)
        self.pen_width_label.setVisible(False)
        self.pen_width_spinbox.setVisible(False)

        # Hide new image controls initially
        self.image_size_label.setVisible(False)
        self.image_width_label.setVisible(False)
        self.image_width_spinbox.setVisible(False)
        self.image_height_label.setVisible(False)
        self.image_height_spinbox.setVisible(False)
        self.save_image_button.setVisible(False)

        theme_colors = self.current_theme_colors

        if self.selected_item:
            item = self.selected_item
            item_type_str = type(item).__name__ # Default item type string

            # Determine capabilities
            can_fill_outline = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPolygonItem))
            is_line = isinstance(item, QGraphicsLineItem)
            is_pen_stroke = isinstance(item, QGraphicsPathItem) and hasattr(item, 'item_type') and item.item_type == 'pen_stroke'
            is_managed_image = isinstance(item, QGraphicsPixmapItem) and hasattr(item, 'pil_original_image')
            can_rotate = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsPixmapItem))

            if can_fill_outline:
                item_type_str = "Shape" # Generic shape, can be refined
                if isinstance(item, QGraphicsRectItem): item_type_str = "Rectangle"
                elif isinstance(item, QGraphicsEllipseItem): item_type_str = "Ellipse"
                elif isinstance(item, QGraphicsPolygonItem) and hasattr(item, 'shape_type') and item.shape_type == 'triangle': item_type_str = "Triangle"
                elif isinstance(item, QGraphicsPolygonItem): item_type_str = "Polygon"
                
                self.fill_color_button.setVisible(True)
                self.current_fill_color_label.setVisible(True)
                self.outline_color_button.setVisible(True)
                self.current_outline_color_label.setVisible(True)
                fill_color = item.brush().color()
                self.current_fill_color_label.setText(f"Fill: {fill_color.name()}")
                self.current_fill_color_label.setStyleSheet(f"background-color: {fill_color.name()}; color: {self.get_contrasting_text_color(fill_color, theme_colors).name()}")
                outline_color = item.pen().color()
                self.current_outline_color_label.setText(f"Outline: {outline_color.name()}")
                self.current_outline_color_label.setStyleSheet(f"background-color: {outline_color.name()}; color: {self.get_contrasting_text_color(outline_color, theme_colors).name()}")

            if is_line:
                item_type_str = "Line"
                self.outline_color_button.setVisible(True)
                self.current_outline_color_label.setVisible(True)
                self.current_fill_color_label.setText("Fill: N/A")
                self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")
                outline_color = item.pen().color()
                self.current_outline_color_label.setText(f"Outline: {outline_color.name()}")
                self.current_outline_color_label.setStyleSheet(f"background-color: {outline_color.name()}; color: {self.get_contrasting_text_color(outline_color, theme_colors).name()}")

            if is_pen_stroke:
                item_type_str = "Pen Stroke"
                self.pen_color_label.setVisible(True)
                self.change_pen_color_button.setVisible(True)
                self.change_pen_color_button.setText("Change Stroke Color")
                self.current_pen_color_preview.setVisible(True)
                self.current_pen_color_preview.setStyleSheet(f"color: {item.pen().color().name()}; font-size: 20px;")
                self.pen_width_label.setVisible(True)
                self.pen_width_spinbox.setVisible(True)
                self.pen_width_spinbox.blockSignals(True)
                self.pen_width_spinbox.setValue(int(item.pen().widthF()))
                self.pen_width_spinbox.blockSignals(False)
                # Hide shape fill/outline if it's a pen stroke, as it's controlled by pen props
                self.fill_color_button.setVisible(False)
                self.current_fill_color_label.setVisible(False)
                self.outline_color_button.setVisible(False)
                self.current_outline_color_label.setVisible(False)

            if is_managed_image:
                item_type_str = "Image"
                self.remove_bg_button.setVisible(True)
                self.brightness_label.setVisible(True)
                self.brightness_slider.setVisible(True)
                self.brightness_value_label.setVisible(True)
                self.start_crop_button.setVisible(True)
                self.apply_crop_button.setVisible(self.current_crop_item == item)
                self.cancel_crop_button.setVisible(self.current_crop_item == item)
                self.save_image_button.setVisible(True) 

                self.image_size_label.setVisible(True)
                self.image_width_label.setVisible(True)
                self.image_width_spinbox.setVisible(True)
                self.image_height_label.setVisible(True)
                self.image_height_spinbox.setVisible(True)
                self._update_image_size_spinboxes(item) # Call helper here
                
                if not self.current_crop_item or self.current_crop_item != item:
                    slider_val = int(item.current_brightness_factor * 100)
                    self.brightness_slider.blockSignals(True)
                    self.brightness_slider.setValue(slider_val)
                    self.brightness_slider.blockSignals(False)
                    self.brightness_value_label.setText(f"{slider_val}%")
                
                # Hide shape fill/outline for images
                self.fill_color_button.setVisible(False)
                self.current_fill_color_label.setVisible(False)
                self.current_fill_color_label.setText("Fill: N/A")
                self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")
                self.current_outline_color_label.setText("Outline: N/A")
                self.current_outline_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")

            if can_rotate:
                self.rotation_label.setVisible(True)
                self.rotation_slider.setVisible(True)
                self.rotation_value_label.setVisible(True)
                self.rotation_slider.blockSignals(True)
                self.rotation_slider.setValue(int(item.rotation()))
                self.rotation_slider.blockSignals(False)
                self.rotation_value_label.setText(f"{int(item.rotation())}°")
            
            # If not an image, ensure image-specific controls are hidden
            if not is_managed_image:
                self.image_size_label.setVisible(False)
                self.image_width_label.setVisible(False)
                self.image_width_spinbox.setVisible(False)
                self.image_height_label.setVisible(False)
                self.image_height_spinbox.setVisible(False)
                self.save_image_button.setVisible(False)
                self.remove_bg_button.setVisible(False)
                self.brightness_label.setVisible(False)
                self.brightness_slider.setVisible(False)
                self.brightness_value_label.setVisible(False)
                self.start_crop_button.setVisible(False)
                self.apply_crop_button.setVisible(False)
                self.cancel_crop_button.setVisible(False)

            self.prop_label.setText(f"Selected: {item_type_str}")

        else: # No item selected
            self.prop_label.setText("Selected: None")
            self.current_fill_color_label.setText("Fill: N/A")
            self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")
            self.current_outline_color_label.setText("Outline: N/A")
            self.current_outline_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")

            # Show pen tool's global properties if pen tool is active
            if self.current_tool == "pen":
                self.pen_color_label.setVisible(True)
                self.change_pen_color_button.setVisible(True)
                self.change_pen_color_button.setText("Change Pen Color")
                self.current_pen_color_preview.setVisible(True)
                self.current_pen_color_preview.setStyleSheet(f"color: {self.current_pen_color.name()}; font-size: 20px;")
                self.pen_width_label.setVisible(True)
                self.pen_width_spinbox.setVisible(True)
                self.pen_width_spinbox.blockSignals(True)
                self.pen_width_spinbox.setValue(int(self.current_pen_width))
                self.pen_width_spinbox.blockSignals(False)
            else:
                # Ensure pen tool's own properties are hidden if no selection and pen tool isn't active
                self.pen_color_label.setVisible(False)
                self.change_pen_color_button.setVisible(False)
                self.current_pen_color_preview.setVisible(False)
                self.pen_width_label.setVisible(False)
                self.pen_width_spinbox.setVisible(False)

    def get_contrasting_text_color(self, bg_color, theme_colors=None):
        # Use current theme's text color as a fallback if bg_color is transparent or similar to it
        # or if no theme_colors provided, attempt to use self.current_theme_colors
        if theme_colors is None:
            theme_colors = self.current_theme_colors if hasattr(self, 'current_theme_colors') else LIGHT_THEME

        if bg_color.alpha() == 0: # Transparent background
            return theme_colors["text_color"]

        # Simple heuristic for contrasting text color (black or white)
        if (bg_color.red() * 0.299 + bg_color.green() * 0.587 + bg_color.blue() * 0.114) > 128: # Adjusted threshold
            # For light backgrounds, prefer dark text
            # Check against the theme's own "text_color" for light backgrounds
            # This part needs refinement: the goal is black or white, not theme's general text color necessarily
            return QColor("black") if theme_colors["name"] == "light" else QColor("black") # Usually black for light bg
        else:
            # For dark backgrounds, prefer light text
            return QColor("white") if theme_colors["name"] == "dark" else QColor("white") # Usually white for dark bg

    def change_selected_item_fill_color(self):
        if self.selected_item and isinstance(self.selected_item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            current_color = self.selected_item.brush().color()
            new_color = QColorDialog.getColor(current_color, self, "Choose Fill Color")
            if new_color.isValid():
                self.selected_item.setBrush(QBrush(new_color))
                self._update_properties_panel_for_selection() # Update display

    def change_selected_item_outline_color(self):
        if self.selected_item and isinstance(self.selected_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem)):
            current_color = self.selected_item.pen().color()
            new_color = QColorDialog.getColor(current_color, self, "Choose Outline Color")
            if new_color.isValid():
                pen = self.selected_item.pen() # Get the current pen
                pen.setColor(new_color)      # Modify its color
                self.selected_item.setPen(pen) # Apply the modified pen
                self.selected_item.update()   # Explicitly schedule a repaint for the item
                self._update_properties_panel_for_selection() # Update display

    def add_image_prompt(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select an Image", 
            "", # Start directory
            "Images (*.png *.xpm *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                image_item = QGraphicsPixmapItem(pixmap)
                image_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable)
                image_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable)
                
                # Store PIL image versions
                q_img_original = pixmap.toImage() # Get QImage from initial pixmap
                pil_img_original = qimage_to_pil(q_img_original)
                image_item.pil_original_image = pil_img_original
                image_item.pil_after_bg_removal = None
                image_item.pil_for_display = pil_img_original.copy()
                image_item.current_brightness_factor = 1.0
                # Ensure pixmap reflects pil_for_display if any conversion differences
                # image_item.setPixmap(QPixmap.fromImage(pil_to_qimage(image_item.pil_for_display))) # Already set from file load

                # Position in the center of the current view
                view_rect = self.view.viewport().rect()
                scene_center_point = self.view.mapToScene(view_rect.center())
                # Adjust for image size to center it
                img_rect = image_item.boundingRect()
                image_item.setPos(scene_center_point - QPointF(img_rect.width()/2, img_rect.height()/2))

                # self.scene.addItem(image_item) # Old direct add
                command = AddItemCommand(image_item, self.scene, "Add Image")
                self.undo_stack.push(command)
            else:
                print(f"Error: Could not load image from {file_path}") # Or show a QMessageBox

    def remove_selected_image_background(self):
        if not self.selected_item or not isinstance(self.selected_item, QGraphicsPixmapItem):
            QMessageBox.information(self, "No Image Selected", "Please select an image to remove its background.")
            return

        try:
            if not hasattr(self.selected_item, 'pil_original_image'):
                QMessageBox.warning(self, "Not a managed image", "This operation is for images loaded by the application.")
                return

            current_qimage = self.selected_item.pixmap().toImage() # Get current QImage from item
            pil_image_to_process = self.selected_item.pil_original_image.copy() # Always use original for BG removal input
            
            # Perform background removal
            processed_pil_image = remove(pil_image_to_process) 
            
            self.selected_item.pil_after_bg_removal = processed_pil_image
            # Brightness factor remains, will be applied by _apply_image_effects
            self._apply_image_effects(self.selected_item)
            
            QMessageBox.information(self, "Background Removed", "Background removal process completed.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove background: {e}")
            print(f"Error removing background: {e}")

    def zoom_in(self):
        self.view.scale(1.2, 1.2)
        self.zoom_factor *= 1.2

    def zoom_out(self):
        self.view.scale(0.8, 0.8)
        self.zoom_factor *= 0.8

    def on_brightness_slider_changed(self, value):
        if self.selected_item and isinstance(self.selected_item, QGraphicsPixmapItem) and hasattr(self.selected_item, 'pil_original_image'):
            new_factor = value / 100.0
            self.selected_item.current_brightness_factor = new_factor
            self.brightness_value_label.setText(f"{value}%") # Update label immediately
            self._apply_image_effects(self.selected_item)
        else:
             # Slider might be visible briefly during selection changes, handle gracefully
            if hasattr(self, 'brightness_value_label'): # Check if UI element exists
                 self.brightness_value_label.setText("--%")

    def _apply_image_effects(self, image_item):
        if not image_item or not hasattr(image_item, 'pil_original_image'):
            return

        base_pil = image_item.pil_after_bg_removal if image_item.pil_after_bg_removal else image_item.pil_original_image
        effect_image = base_pil.copy()

        # Apply Brightness
        if hasattr(image_item, 'current_brightness_factor'):
            enhancer = ImageEnhance.Brightness(effect_image)
            effect_image = enhancer.enhance(image_item.current_brightness_factor)
        
        # --- Future effects (e.g., contrast) would be applied here to effect_image ---
        # Example: Contrast
        # if hasattr(image_item, 'current_contrast_factor'):
        #     enhancer_contrast = ImageEnhance.Contrast(effect_image)
        #     effect_image = enhancer_contrast.enhance(image_item.current_contrast_factor)

        image_item.pil_for_display = effect_image
        new_qimage = pil_to_qimage(image_item.pil_for_display)
        image_item.setPixmap(QPixmap.fromImage(new_qimage))
        image_item.modifiable_qimage = None # Invalidate eraser's cached QImage

    def apply_theme(self, theme_name):
        if theme_name not in self.themes:
            print(f"Error: Theme '{theme_name}' not found.")
            return
        
        self.current_theme_name = theme_name
        self.current_theme_colors = self.themes[theme_name]
        theme = self.current_theme_colors

        # Format stylesheet with actual color values
        formatted_stylesheet = theme["stylesheet"].format(
            window_bg=theme["window_bg"].name(),
            text_color=theme["text_color"].name(),
            button_bg=theme["button_bg"].name(),
            button_text=theme["text_color"].name(), # Assuming button text is same as general text
            toolbar_bg=theme["toolbar_bg"].name(),
            properties_bg=theme["properties_bg"].name()
        )
        self.setStyleSheet(formatted_stylesheet)
        
        # Explicitly set background for dock widget and its content area if stylesheet is not enough
        self.properties_dock.setStyleSheet(f"QDockWidget {{ background-color: {theme['properties_bg'].name()}; color: {theme['text_color'].name()}; }} QDockWidget::title {{ background-color: {theme['toolbar_bg'].name()}; border: 1px solid #b0b0b0; padding: 4px; color: {theme['text_color'].name()}; }}")
        self.properties_widget.setStyleSheet(f"QWidget {{ background-color: {theme['properties_bg'].name()}; color: {theme['text_color'].name()}; }}")

        if self.custom_canvas_bg_color:
            self.scene.setBackgroundBrush(self.custom_canvas_bg_color)
        else:
            self.scene.setBackgroundBrush(theme["canvas_bg"])

        # Update properties panel labels' text color (buttons are handled by stylesheet)
        self.prop_label.setStyleSheet(f"color: {theme['text_color'].name()};")
        self.current_fill_color_label.setStyleSheet(f"color: {theme['text_color'].name()}; background-color: transparent;") # Reset bg, color set by value
        self.current_outline_color_label.setStyleSheet(f"color: {theme['text_color'].name()}; background-color: transparent;") # Reset bg, color set by value
        self._update_properties_panel_for_selection() # Re-render to apply color previews with new text contrast

        # Update existing items (optional, could be complex if many items)
        # For now, new items will use the theme. Existing items retain their colors unless explicitly changed.
        # However, resize handles should update
        if self.selected_item:
            self._update_resize_handles_for_item(self.selected_item) # Re-create with new theme colors
        
        self.scene.update() # Redraw scene
        print(f"Applied {theme_name} theme.")

    def delete_selected_item(self):
        if self.selected_item:
            item_to_delete = self.selected_item
            self.scene.removeItem(item_to_delete)
            self._remove_resize_handles() # Clear handles for the deleted item
            self.selected_item = None
            # If the deleted item had specific data stored (e.g. PIL image for QGraphicsPixmapItem)
            # ensure it's cleaned up if necessary to avoid memory leaks.
            # For now, basic item removal is handled.
            del item_to_delete # Explicitly delete the Python reference
            self._update_properties_panel_for_selection() # Update panel to show no selection
            print("Item deleted")
        else:
            print("No item selected to delete")

    def change_canvas_background_color(self):
        current_color = self.scene.backgroundBrush().color()
        new_color = QColorDialog.getColor(current_color, self, "Choose Canvas Background Color")
        if new_color.isValid():
            self.custom_canvas_bg_color = new_color # Store custom choice
            self.scene.setBackgroundBrush(new_color)
            self.scene.update()

    def enter_crop_mode(self):
        print("enter_crop_mode called.")
        if not self.selected_item:
            print("enter_crop_mode: No item selected.")
            QMessageBox.warning(self, "Cannot Crop", "No item selected. Please select an image loaded by the application to crop.")
            return
        
        print(f"enter_crop_mode: Selected item is {type(self.selected_item)}, has pil_original_image: {hasattr(self.selected_item, 'pil_original_image')}")

        if not isinstance(self.selected_item, QGraphicsPixmapItem) or not hasattr(self.selected_item, 'pil_original_image'):
            print("enter_crop_mode: Selected item is not a valid image for cropping.")
            QMessageBox.warning(self, "Cannot Crop", "Please select an image loaded by the application to crop.")
            return

        print("enter_crop_mode: Proceeding with crop mode setup.")

        if self.current_crop_item: # Already cropping another item? Or re-clicked on same item?
            print(f"enter_crop_mode: Already in crop mode for {self.current_crop_item}. Current selection: {self.selected_item}")
            if self.current_crop_item == self.selected_item:
                # Clicked "Crop Image" again for the item already in crop mode - do nothing or treat as cancel?
                # For now, let's assume this state shouldn't be easily reachable if UI updates correctly.
                return 
            else:
                # Switched selection while an old crop was active - cancel old one first
                print("enter_crop_mode: Switching crop target, cancelling old crop.")
                self.exit_crop_mode(apply_changes=False) 

        item_to_crop = self.selected_item # Store it before it gets deselected
        if not item_to_crop: # Should have been caught earlier, but as a safeguard
            print("enter_crop_mode: Error - item_to_crop became None unexpectedly.")
            return

        self.current_crop_item = item_to_crop
        self._remove_resize_handles() # Remove item resize handles, as we'll use crop handles
        
        # Deselect the item. This will trigger on_scene_selection_changed, which sets self.selected_item to None.
        # That's fine, as we are now using item_to_crop and self.current_crop_item.
        item_to_crop.setSelected(False) 
        item_to_crop.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, False) # Disable moving base image

        # Create visual crop rectangle as a child of the image item
        # It uses the image's local coordinates.
        img_brect = self.current_crop_item.boundingRect() # This is in item's local coords
        self.crop_overlay_rect = QGraphicsRectItem(img_brect, self.current_crop_item) # Child item
        self.crop_overlay_rect.setPen(QPen(QColor("yellow"), 2, Qt.PenStyle.DashLine)) # Visible dashing outline
        self.crop_overlay_rect.setBrush(QColor(0,0,0,80)) # Semi-transparent overlay
        # Make it non-interactive itself, handles will do the work
        self.crop_overlay_rect.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False) 
        self.crop_overlay_rect.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, False)

        self._create_crop_handles() # Create handles for self.crop_overlay_rect

        self._update_properties_panel_for_selection() # Update buttons
        self.view.setFocus() # Ensure view has focus for potential keyboard shortcuts (e.g. Esc for cancel)
        print(f"Entering crop mode for {self.current_crop_item}")

    def _create_crop_handles(self):
        self._remove_crop_handles() # Clear any existing crop handles
        if not self.crop_overlay_rect or not self.current_crop_item:
            return

        parent_for_handles = self.crop_overlay_rect
        rect_to_handle = self.crop_overlay_rect.rect() # In crop_overlay_rect's local coords (0,0 top-left)

        handle_positions = {
            "nw_crop": QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "n_crop":  QPointF(rect_to_handle.center().x() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "ne_crop": QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "w_crop":  QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.center().y() - HANDLE_SIZE / 2),
            "e_crop":  QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.center().y() - HANDLE_SIZE / 2),
            "sw_crop": QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
            "s_crop":  QPointF(rect_to_handle.center().x() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
            "se_crop": QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
        }

        for handle_type, pos in handle_positions.items():
            handle = QGraphicsRectItem(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent_for_handles)
            handle.setPos(pos)
            handle.setBrush(self.current_theme_colors["selected_handle_fill"])
            handle.setPen(QPen(self.current_theme_colors["selected_handle_outline"], 1))
            handle.is_crop_handle = True
            handle.handle_type = handle_type
            handle.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
            self.active_crop_handles.append(handle)

    def _update_crop_handles(self):
        if not self.active_crop_handles or not self.crop_overlay_rect: return
        rect_to_handle = self.crop_overlay_rect.rect()

        # Define desired positions based on the current rect_to_handle
        new_handle_positions = {
            "nw_crop": QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "n_crop":  QPointF(rect_to_handle.center().x() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "ne_crop": QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.top() - HANDLE_SIZE / 2),
            "w_crop":  QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.center().y() - HANDLE_SIZE / 2),
            "e_crop":  QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.center().y() - HANDLE_SIZE / 2),
            "sw_crop": QPointF(rect_to_handle.left() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
            "s_crop":  QPointF(rect_to_handle.center().x() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
            "se_crop": QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2),
        }

        for handle in self.active_crop_handles:
            if handle.handle_type in new_handle_positions:
                handle.setPos(new_handle_positions[handle.handle_type])
                # Also update handle colors in case theme changed while active
                handle.setBrush(self.current_theme_colors["selected_handle_fill"])
                handle.setPen(QPen(self.current_theme_colors["selected_handle_outline"], 1))

    def _remove_crop_handles(self):
        # Iterate over a copy if modifying the list, or just clear after scene removal
        for handle in list(self.active_crop_handles): # Iterate a copy
            if handle and handle.scene(): # Check if handle is not None and still in a scene
                self.scene.removeItem(handle)
        self.active_crop_handles.clear()

    def exit_crop_mode(self, apply_changes=False):
        if not self.current_crop_item:
            return
        
        item_was_cropped = self.current_crop_item

        # Store crop_overlay_rect locally because self.crop_overlay_rect will be set to None
        local_crop_overlay_rect = self.crop_overlay_rect

        if apply_changes and local_crop_overlay_rect:
            # 1. Get crop rectangle in item's local coordinates.
            crop_box_item_coords = local_crop_overlay_rect.rect()

            # 2. Ensure crop_box is valid (e.g., positive width/height)
            if crop_box_item_coords.width() < 1 or crop_box_item_coords.height() < 1:
                QMessageBox.warning(self, "Invalid Crop", "Crop area is too small.")
                # Don't exit crop mode, let user adjust
                return 
            
            # Convert to integer tuple for PIL crop (x, y, x+width, y+height)
            # PIL crop box is (left, upper, right, lower)
            pil_crop_box = (
                int(crop_box_item_coords.left()),
                int(crop_box_item_coords.top()),
                int(crop_box_item_coords.right()),
                int(crop_box_item_coords.bottom())
            )

            # --- Perform actual cropping on PIL images --- 
            cropped_something = False
            try:
                # A. Crop pil_original_image
                if item_was_cropped.pil_original_image:
                    item_was_cropped.pil_original_image = item_was_cropped.pil_original_image.crop(pil_crop_box)
                    cropped_something = True
                
                # B. Crop pil_after_bg_removal (if it exists)
                if item_was_cropped.pil_after_bg_removal:
                    item_was_cropped.pil_after_bg_removal = item_was_cropped.pil_after_bg_removal.crop(pil_crop_box)
                    # No need to set cropped_something again if already true

                # C. Re-apply effects to get new pil_for_display
                if cropped_something:
                    self._apply_image_effects(item_was_cropped) # This will update pil_for_display and the pixmap
                else: # Should not happen if we selected an image
                    self.exit_crop_mode(apply_changes=False) # Effectively a cancel
                    return

                # 3. Adjust QGraphicsPixmapItem's position if crop changed its top-left origin.
                # The new pixmap from _apply_image_effects is based on the cropped PIL images.
                # Its (0,0) corresponds to the crop_box_item_coords.topLeft().
                # We need to translate the item by this amount.
                offset = crop_box_item_coords.topLeft()
                item_was_cropped.setPos(item_was_cropped.pos() + offset)
                # Bounding rect of the QGraphicsPixmapItem will change automatically due to new pixmap.

                print(f"Applied crop to {item_was_cropped}")

            except Exception as e:
                QMessageBox.critical(self, "Crop Error", f"Could not apply crop: {e}")
                print(f"Error during PIL crop: {e}")
        
        # Cleanup UI
        self._remove_crop_handles() # Call this first to remove handles from scene before their parent overlay is gone
                                  # This assumes handles are NOT children of crop_overlay_rect for this to work, 
                                  # or that _remove_crop_handles is safe against already deleted items.
                                  # Current _create_crop_handles makes them children. So this is problematic.

        # Revised cleanup:
        # 1. Remove handles explicitly IF they are not children or if we want to be sure before parent removal.
        #    However, _create_crop_handles makes them children of crop_overlay_rect.
        #    So, removing crop_overlay_rect should remove the handles. Our list just needs clearing.

        if self.crop_overlay_rect: # Check if it exists
            self.scene.removeItem(self.crop_overlay_rect)
            self.crop_overlay_rect = None # This should trigger Qt to delete children (handles)
        
        self.active_crop_handles.clear() # Clear our Python list of handles
        
        item_was_cropped.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True) # Re-enable moving
        item_was_cropped.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsSelectable, True) # Ensure it's selectable
        item_was_cropped.setSelected(True) 

        self.current_crop_item = None
        self._update_properties_panel_for_selection() # Update buttons

    def change_pen_color(self):
        new_color = QColorDialog.getColor(self.current_pen_color, self, "Choose Pen Color")
        if new_color.isValid():
            self.current_pen_color = new_color
            if self.current_tool == "pen": # Update preview only if pen tool is active
                self.current_pen_color_preview.setStyleSheet(f"color: {self.current_pen_color.name()}; font-size: 20px;")
            elif self.selected_item and isinstance(self.selected_item, QGraphicsPathItem) and hasattr(self.selected_item, 'item_type') and self.selected_item.item_type == 'pen_stroke':
                pen = self.selected_item.pen()
                pen.setColor(new_color)
                self.selected_item.setPen(pen)
                self.current_pen_color_preview.setStyleSheet(f"color: {new_color.name()}; font-size: 20px;") # Update preview for selected item
                self.selected_item.update()

    def on_pen_width_changed(self, value):
        new_width = float(value)
        if self.current_tool == "pen":
            self.current_pen_width = new_width
            print(f"Pen tool width changed to: {self.current_pen_width}")
        elif self.selected_item and isinstance(self.selected_item, QGraphicsPathItem) and hasattr(self.selected_item, 'item_type') and self.selected_item.item_type == 'pen_stroke':
            pen = self.selected_item.pen()
            pen.setWidthF(new_width)
            self.selected_item.setPen(pen)
            self.selected_item.update()
            print(f"Selected stroke width changed to: {new_width}")

    def on_rotation_slider_changed(self, value):
        if self.selected_item and isinstance(self.selected_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPathItem, QGraphicsPolygonItem, QGraphicsPixmapItem)):
            angle = float(value)
            self.selected_item.setRotation(angle)
            self.rotation_value_label.setText(f"{int(angle)}°")
            self._update_resize_handles_for_item(self.selected_item) 
        else:
            if hasattr(self, 'rotation_value_label'): # Check if UI element exists
                 self.rotation_value_label.setText("--°")

    # --- Z-Order Methods ---
    def _get_all_z_values(self):
        return sorted([item.zValue() for item in self.scene.items()])

    def bring_selected_to_front(self):
        if self.selected_item:
            all_z_values = self._get_all_z_values()
            if all_z_values:
                max_z = all_z_values[-1]
                self.selected_item.setZValue(max_z + 1)
            else: # Only item in scene
                self.selected_item.setZValue(1) # Start with 1 if it's the first
            self.scene.update()

    def send_selected_to_back(self):
        if self.selected_item:
            all_z_values = self._get_all_z_values()
            if all_z_values:
                min_z = all_z_values[0]
                self.selected_item.setZValue(min_z - 1)
            else: # Only item in scene
                self.selected_item.setZValue(-1) # Start with -1 if it's the first
            self.scene.update()

    def bring_selected_forward(self):
        if self.selected_item:
            current_z = self.selected_item.zValue()
            # Find the smallest z-value strictly greater than current_z
            next_z_values = sorted([item.zValue() for item in self.scene.items() if item.zValue() > current_z])
            if next_z_values:
                # If there's an item directly in front with a different z-value, 
                # place this item just above that one. 
                # A simple increment is usually enough if z-values are somewhat sparse.
                # To be more robust and avoid large gaps or too small increments:
                # Find the item that is visually just above the current one.
                # This can be complex. A simpler approach for now is to increment. 
                # If we want to swap with the item directly in front: 
                # Get all items, sort by Z. Find index of current_item. 
                # If not at top, find Z of item[index+1]. Set current_item Z to Z_item_above + epsilon.
                # For now, just incrementing Z. This might lead to large Z values over time.
                self.selected_item.setZValue(current_z + 1) 
            else:
                # Already at the front relative to other z-values, ensure it's max_z + 1 if not already
                all_z = self._get_all_z_values()
                if all_z and current_z < all_z[-1]: # Should not happen if next_z_values is empty
                     self.selected_item.setZValue(all_z[-1] + 1)
                # If it is already the highest, incrementing it further is fine.
                elif all_z and current_z == all_z[-1]:
                    self.selected_item.setZValue(current_z + 0.1) # Small increment to break ties or ensure it's distinct if needed
                else: # Only item or already highest
                    self.selected_item.setZValue(current_z + 0.1)

            self.scene.update()

    def send_selected_backward(self):
        if self.selected_item:
            current_z = self.selected_item.zValue()
            # Find the largest z-value strictly smaller than current_z
            prev_z_values = sorted([item.zValue() for item in self.scene.items() if item.zValue() < current_z], reverse=True)
            if prev_z_values:
                # Similar logic to bring_selected_forward, but decrementing.
                self.selected_item.setZValue(current_z - 1) 
            else:
                # Already at the back relative to other z-values
                all_z = self._get_all_z_values()
                if all_z and current_z > all_z[0]:
                    self.selected_item.setZValue(all_z[0] -1)
                elif all_z and current_z == all_z[0]:
                     self.selected_item.setZValue(current_z - 0.1)
                else:
                    self.selected_item.setZValue(current_z - 0.1)
            self.scene.update()

    # --- Image Saving Method ---
    def save_selected_image_as(self):
        if not self.selected_item:
            QMessageBox.information(self, "No Selection", "Please select an item to save.")
            return

        if not isinstance(self.selected_item, QGraphicsPixmapItem):
            QMessageBox.warning(self, "Cannot Save", "The selected item is not a savable image (e.g., shape). Please select an image.")
            return

        item_to_save = self.selected_item
        pixmap_to_render = item_to_save.pixmap() # This should have effects applied

        if pixmap_to_render.isNull():
            QMessageBox.critical(self, "Error", "Image data is missing or invalid for the selected item.")
            return

        # Get the item's bounding rectangle in scene coordinates
        target_rect_scene = item_to_save.sceneBoundingRect()
        output_image_size = target_rect_scene.size().toSize()
        
        # Ensure minimum size for output image if rect is too small (e.g. fully scaled down)
        if output_image_size.width() < 1 or output_image_size.height() < 1:
            # Fallback: try to render at least the original pixmap size, or a small default
            if not pixmap_to_render.isNull():
                output_image_size = pixmap_to_render.size()
            if output_image_size.width() < 1 or output_image_size.height() < 1: # Still invalid
                 QMessageBox.warning(self, "Save Error", "Image is too small to render.")
                 return

        # Create the output QImage
        rendered_qimage = QImage(output_image_size, QImage.Format_ARGB32_Premultiplied)
        rendered_qimage.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rendered_qimage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # The painter's world transform needs to map the item's local (pixmap) coordinates 
        # to the correct position within our rendered_qimage.
        # 1. Start with identity on painter for rendered_qimage.
        # 2. We want the item_to_save.sceneBoundingRect().topLeft() to map to (0,0) in rendered_qimage.
        #    So, translate the painter by -item_to_save.sceneBoundingRect().topLeft().
        # 3. Then, apply the item's full sceneTransform() to the painter.
        # 4. Draw the item's original pixmap at (0,0) in item's local coords.

        painter.translate(-target_rect_scene.topLeft())
        painter.setTransform(item_to_save.sceneTransform(), True) # True to combine with existing translation
        
        # Draw the source pixmap (which is in item's local coords, starting at 0,0 for pixmap item)
        painter.drawPixmap(QPointF(0,0), pixmap_to_render) 
        painter.end()

        pil_image_to_save = qimage_to_pil(rendered_qimage)

        if not pil_image_to_save:
            QMessageBox.critical(self, "Error", "Could not render the selected image for saving.")
            return

        suggested_filename = "rendered_image.png" 

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Image As...",
            suggested_filename, # Default/suggested filename
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;Bitmap Image (*.bmp);;GIF Image (*.gif);;All Files (*)"
        )

        if file_path:
            try:
                # PIL infers format from extension. For formats like JPEG that don't support alpha,
                # you might want to convert the image mode.
                if pil_image_to_save.mode == 'RGBA' and (file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg')):
                    # Convert to RGB if saving as JPEG to avoid potential errors with alpha channel
                    image_to_save_final = pil_image_to_save.convert('RGB')
                    image_to_save_final.save(file_path)
                else:
                    pil_image_to_save.save(file_path)
                QMessageBox.information(self, "Image Saved", f"Image successfully saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save image:\n{e}")
                print(f"Error saving image to {file_path}: {e}")
        else:
            print("Save operation cancelled by user.")

    # --- Image Size Change Handlers (New) ---
    def on_image_width_editing_finished(self):
        if not self.selected_item or not isinstance(self.selected_item, QGraphicsPixmapItem) or not hasattr(self.selected_item, 'pil_original_image'):
            return
        
        item = self.selected_item
        desired_width = self.image_width_spinbox.value()
        # Use the current value from the other spinbox for the other dimension
        desired_height = self.image_height_spinbox.value() 

        final_width = max(desired_width, MIN_SHAPE_SIZE)
        final_height = max(desired_height, MIN_SHAPE_SIZE) # Constrain the other dimension too

        original_pixmap = item.pixmap()
        original_pixmap_width = original_pixmap.width()
        original_pixmap_height = original_pixmap.height()

        if original_pixmap_width == 0 or original_pixmap_height == 0:
            # Cannot scale, reset spinboxes to some minimum or current (likely small) brect
            self.image_width_spinbox.blockSignals(True)
            self.image_height_spinbox.blockSignals(True)
            self.image_width_spinbox.setValue(max(int(item.boundingRect().width()), int(MIN_SHAPE_SIZE)))
            self.image_height_spinbox.setValue(max(int(item.boundingRect().height()), int(MIN_SHAPE_SIZE)))
            self.image_width_spinbox.blockSignals(False)
            self.image_height_spinbox.blockSignals(False)
            return 

        scale_x = final_width / original_pixmap_width
        scale_y = final_height / original_pixmap_height

        current_rotation = item.rotation()
        transform = QTransform().scale(scale_x, scale_y).rotate(current_rotation)
        item.setTransform(transform)
        
        self._update_resize_handles_for_item(item)

        # Update spinboxes to the exact values used for scaling (after constraints)
        self.image_width_spinbox.blockSignals(True)
        self.image_width_spinbox.setValue(int(round(final_width)))
        self.image_width_spinbox.blockSignals(False)

        self.image_height_spinbox.blockSignals(True)
        self.image_height_spinbox.setValue(int(round(final_height)))
        self.image_height_spinbox.blockSignals(False)
        
        self.scene.update() 

    def on_image_height_editing_finished(self):
        if not self.selected_item or not isinstance(self.selected_item, QGraphicsPixmapItem) or not hasattr(self.selected_item, 'pil_original_image'):
            return

        item = self.selected_item
        desired_width = self.image_width_spinbox.value()
        desired_height = self.image_height_spinbox.value()

        final_width = max(desired_width, MIN_SHAPE_SIZE) # Constrain the other dimension too
        final_height = max(desired_height, MIN_SHAPE_SIZE)

        original_pixmap = item.pixmap()
        original_pixmap_width = original_pixmap.width()
        original_pixmap_height = original_pixmap.height()

        if original_pixmap_width == 0 or original_pixmap_height == 0:
            self.image_width_spinbox.blockSignals(True)
            self.image_height_spinbox.blockSignals(True)
            self.image_width_spinbox.setValue(max(int(item.boundingRect().width()), int(MIN_SHAPE_SIZE)))
            self.image_height_spinbox.setValue(max(int(item.boundingRect().height()), int(MIN_SHAPE_SIZE)))
            self.image_width_spinbox.blockSignals(False)
            self.image_height_spinbox.blockSignals(False)
            return

        scale_x = final_width / original_pixmap_width
        scale_y = final_height / original_pixmap_height 

        current_rotation = item.rotation()
        transform = QTransform().scale(scale_x, scale_y).rotate(current_rotation)
        item.setTransform(transform)

        self._update_resize_handles_for_item(item)
        
        self.image_width_spinbox.blockSignals(True)
        self.image_width_spinbox.setValue(int(round(final_width)))
        self.image_width_spinbox.blockSignals(False)

        self.image_height_spinbox.blockSignals(True)
        self.image_height_spinbox.setValue(int(round(final_height)))
        self.image_height_spinbox.blockSignals(False)
        
        self.scene.update()

    def _update_image_size_spinboxes(self, item_or_none):
        """Helper to update spinboxes from item's current state, primarily for selection and after mouse resize."""
        if item_or_none and isinstance(item_or_none, QGraphicsPixmapItem) and self.image_width_spinbox.isVisible():
            item = item_or_none
            pixmap_w = item.pixmap().width()
            pixmap_h = item.pixmap().height()
            
            content_w, content_h = MIN_SHAPE_SIZE, MIN_SHAPE_SIZE # Defaults

            if pixmap_w > 0 and pixmap_h > 0:
                # Use item.scale() which reflects uniform scaling (typically from mouse resize)
                # If item.transform() was set with non-uniform scale, item.scale() might be 1.0 or less informative.
                # In such a case, the spinboxes would have been the last source of truth for content size.
                # This method is for refreshing on selection or after a uniform (mouse) scale.
                s = item.scale() 
                calculated_w = pixmap_w * s
                calculated_h = pixmap_h * s
                
                # If the transform is non-identity and suggests non-uniform scaling not captured by item.scale(),
                # it's hard to perfectly get back to the "intended content size" without storing it explicitly.
                # For now, rely on item.scale() for this refresh.
                content_w = max(calculated_w, MIN_SHAPE_SIZE)
                content_h = max(calculated_h, MIN_SHAPE_SIZE)
            else: # Pixmap has no dimensions
                # If item has a bounding rect (e.g. it was a shape converted to pixmap badly)
                brect = item.boundingRect()
                content_w = max(brect.width(), MIN_SHAPE_SIZE)
                content_h = max(brect.height(), MIN_SHAPE_SIZE)

            self.image_width_spinbox.blockSignals(True)
            self.image_height_spinbox.blockSignals(True)
            self.image_width_spinbox.setValue(int(round(content_w)))
            self.image_height_spinbox.setValue(int(round(content_h)))
            self.image_width_spinbox.blockSignals(False)
            self.image_height_spinbox.blockSignals(False)
        elif not item_or_none and self.image_width_spinbox.isVisible(): 
            self.image_width_spinbox.blockSignals(True)
            self.image_height_spinbox.blockSignals(True)
            self.image_width_spinbox.setValue(self.image_width_spinbox.minimum() if self.image_width_spinbox.minimum() > 0 else 1) 
            self.image_height_spinbox.setValue(self.image_height_spinbox.minimum() if self.image_height_spinbox.minimum() > 0 else 1)
            self.image_width_spinbox.blockSignals(False)
            self.image_height_spinbox.blockSignals(False)

    # --- Table Pasting Method ---
    def paste_table_from_clipboard(self, scene_pos):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()

        if not mime_data.hasText():
            QMessageBox.information(self, "Paste Error", "No text data found on clipboard.")
            return

        clipboard_text = mime_data.text()
        if not clipboard_text.strip():
            QMessageBox.information(self, "Paste Error", "Clipboard text is empty.")
            return

        # Try to parse as TSV (Tab Separated Values) then CSV
        parsed_rows = []
        try:
            # Use StringIO to treat the string as a file for csv.reader
            f = StringIO(clipboard_text)
            # Attempt to sniff the dialect
            dialect = None
            try:
                dialect = csv.Sniffer().sniff(clipboard_text.splitlines()[0]) # Sniff first line
            except csv.Error:
                # Sniffing failed, try common delimiters
                if '\t' in clipboard_text.splitlines()[0]:
                    dialect = csv.excel_tab
                else:
                    dialect = csv.excel # Default to Excel (comma-separated)
            
            reader = csv.reader(f, dialect)
            for row in reader:
                parsed_rows.append(row)
        except Exception as e:
            QMessageBox.warning(self, "Parse Error", f"Could not parse table data: {e}")
            return

        if not parsed_rows:
            QMessageBox.information(self, "Paste Error", "No rows found in pasted table data.")
            return

        # --- Create Table Graphics ---
        table_group = QGraphicsItemGroup()
        table_group.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable, True)
        table_group.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable, True)
        # table_group.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemSendsGeometryChanges, True) # For future resizing

        # Default cell styling and dimensions
        cell_padding = 5.0
        default_cell_width = 100.0 
        default_cell_height = 30.0
        theme_colors = self.current_theme_colors
        cell_border_pen = QPen(theme_colors["item_default_outline"])
        cell_fill_brush = QBrush(theme_colors["window_bg"]) # Use window_bg for cells, or a lighter properties_bg
        text_color = theme_colors["text_color"]

        current_y = 0.0
        max_cols = max(len(row) for row in parsed_rows) if parsed_rows else 0

        for row_idx, row_data in enumerate(parsed_rows):
            current_x = 0.0
            row_actual_height = default_cell_height # Could calculate based on text in future
            for col_idx in range(max_cols):
                cell_text_content = row_data[col_idx] if col_idx < len(row_data) else ""
                cell_actual_width = default_cell_width # Could calculate based on text

                # Create cell rectangle (background and border)
                cell_rect_item = QGraphicsRectItem(0, 0, cell_actual_width, row_actual_height, table_group)
                cell_rect_item.setPos(current_x, current_y)
                cell_rect_item.setPen(cell_border_pen)
                cell_rect_item.setBrush(cell_fill_brush)

                # Create cell text
                text_item = QGraphicsSimpleTextItem(cell_text_content, table_group)
                text_item.setPos(current_x + cell_padding, current_y + cell_padding)
                text_item.setBrush(QBrush(text_color)) 
                # text_item.setFont(...) # Can set font here
                
                # Ensure text does not overflow cell_actual_width - 2*cell_padding (approx)
                # QGraphicsSimpleTextItem does not auto-wrap or clip aggressively. 
                # For proper handling, QGraphicsTextItem would be needed, or manual truncation.
                # This is a simple start.

                current_x += cell_actual_width
            current_y += row_actual_height
        
        table_group.setPos(scene_pos)
        # self.scene.addItem(table_group) # Old direct add
        command = AddItemCommand(table_group, self.scene, "Paste Table")
        self.undo_stack.push(command)
        # table_group.setSelected(True) # AddItemCommand.redo() handles selection
        print("Table pasted successfully.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CanvasWindow()
    window.show()
    sys.exit(app.exec()) 