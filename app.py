import sys
from io import BytesIO
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QToolBar, QDockWidget, QWidget, QVBoxLayout, QLabel, QPushButton, QRadioButton,
    QGraphicsRectItem, QGraphicsEllipseItem, QToolButton, QMenu, QColorDialog, QGraphicsLineItem, QFileDialog, QGraphicsPixmapItem, QMessageBox,
    QMenuBar, QSlider, QSpinBox, QGraphicsPathItem # Added QGraphicsPathItem here
)
from PySide6.QtGui import QAction, QIcon, QColor, QPainter, QPen, QBrush, QImage, QPixmap, QPainterPath # Removed from here
from PySide6.QtCore import Qt, QRectF, QPointF, QSizeF, QBuffer

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

    def mousePressEvent(self, event):
        tool = self.parent_window.current_tool
        
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos_scene = self.mapToScene(event.position().toPoint())

            if tool == "select":
                item_at_click = self.itemAt(event.position().toPoint())
                if item_at_click and hasattr(item_at_click, 'is_resize_handle'): # Check if it's one of our handles
                    self.item_being_resized = item_at_click.parentItem()
                    self.current_resize_handle_type = item_at_click.handle_type
                    self.resize_start_pos_scene = self.start_pos_scene # Use mapped scene coords
                    if self.item_being_resized: # Ensure parent is valid
                        self.original_item_rect_on_resize_start = self.item_being_resized.rect()
                    else: # Should not happen if handle is correctly parented
                        self.current_resize_handle_type = None 
                        return
                    event.accept()
                    return # Handled resize press
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
        current_pos_scene = self.mapToScene(event.position().toPoint()) # Define here for general access
        theme_colors = self.parent_window.current_theme_colors

        if self.item_being_resized and self.current_resize_handle_type and (event.buttons() & Qt.MouseButton.LeftButton):
            # current_pos_scene is already available
            
            # Ensure item_being_resized is still valid (e.g., not deleted)
            if not self.item_being_resized or not self.item_being_resized.scene(): 
                self.item_being_resized = None # Invalidate if item disappeared
                self.current_resize_handle_type = None
                return

            dx = current_pos_scene.x() - self.resize_start_pos_scene.x()
            dy = current_pos_scene.y() - self.resize_start_pos_scene.y()

            new_rect = QRectF(self.original_item_rect_on_resize_start)

            if self.current_resize_handle_type == "se":
                new_rect.setBottomRight(QPointF(new_rect.bottomRight().x() + dx, new_rect.bottomRight().y() + dy))
            
            # Add other handle types here later (nw, ne, sw, n, s, e, w)

            # Enforce minimum size
            if new_rect.width() < MIN_SHAPE_SIZE:
                new_rect.setWidth(MIN_SHAPE_SIZE)
            if new_rect.height() < MIN_SHAPE_SIZE:
                new_rect.setHeight(MIN_SHAPE_SIZE)
            
            self.item_being_resized.setRect(new_rect.normalized())
            self.parent_window._update_resize_handles_for_item(self.item_being_resized) # Update handle positions
            event.accept()
            return # Handled resize move
        
        # --- Drawing tools preview logic ---
        elif self.start_pos_scene and (event.buttons() & Qt.MouseButton.LeftButton) and tool in ["rectangle", "ellipse", "line"]:
            # current_pos_scene is already available
            if self.current_preview_item_view:
                self.scene().removeItem(self.current_preview_item_view)
                self.current_preview_item_view = None
            
            pen = QPen(theme_colors["preview_dash_color"]) # Use themed preview color
            pen.setStyle(Qt.PenStyle.DashLine)

            if tool == "rectangle":
                self.current_preview_item_view = QGraphicsRectItem(QRectF(self.start_pos_scene, current_pos_scene).normalized())
            elif tool == "ellipse":
                self.current_preview_item_view = QGraphicsEllipseItem(QRectF(self.start_pos_scene, current_pos_scene).normalized())
            elif tool == "line":
                self.current_preview_item_view = QGraphicsLineItem(self.start_pos_scene.x(), self.start_pos_scene.y(),
                                                                   current_pos_scene.x(), current_pos_scene.y())
            
            if self.current_preview_item_view:
                self.current_preview_item_view.setPen(pen)
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

    def mouseReleaseEvent(self, event):
        tool = self.parent_window.current_tool
        theme_colors = self.parent_window.current_theme_colors

        if self.item_being_resized and event.button() == Qt.MouseButton.LeftButton:
            self.item_being_resized = None
            self.current_resize_handle_type = None
            self.resize_start_pos_scene = None
            self.original_item_rect_on_resize_start = None
            event.accept()
            # Update handles one last time, just in case
            if self.parent_window.selected_item:
                 self.parent_window._update_resize_handles_for_item(self.parent_window.selected_item)
            return # Handled resize release

        # --- Drawing tools finalization logic ---
        if event.button() == Qt.MouseButton.LeftButton and self.start_pos_scene and tool in ["rectangle", "ellipse", "line"]:
            current_pos_scene = self.mapToScene(event.position().toPoint())
            if self.current_preview_item_view:
                self.scene().removeItem(self.current_preview_item_view)
                self.current_preview_item_view = None

            final_item = None
            outline_color = theme_colors["item_default_outline"]
            pen = QPen(outline_color)

            if tool == "rectangle" or tool == "ellipse":
                final_rect = QRectF(self.start_pos_scene, current_pos_scene).normalized()
                if final_rect.width() >= MIN_SHAPE_SIZE and final_rect.height() >= MIN_SHAPE_SIZE:
                    fill_color = theme_colors["item_default_fill"]
                    if tool == "rectangle":
                        final_item = QGraphicsRectItem(final_rect)
                    elif tool == "ellipse":
                        final_item = QGraphicsEllipseItem(final_rect)
                    if final_item:
                        final_item.setBrush(QBrush(fill_color))
            elif tool == "line":
                # Check for minimal length for a line, if desired (e.g., avoid zero-length lines)
                if (self.start_pos_scene - current_pos_scene).manhattanLength() > MIN_SHAPE_SIZE / 2:
                    final_item = QGraphicsLineItem(self.start_pos_scene.x(), self.start_pos_scene.y(),
                                                   current_pos_scene.x(), current_pos_scene.y())
            
            if final_item:
                final_item.setPen(pen)
                final_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
                final_item.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
                self.scene().addItem(final_item)
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
            self.current_drawing_path_item = None # Reset for next stroke
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
        self.active_resize_handles = [] # Store current active handles
        self.zoom_factor = 1.0 # Initialize zoom factor
        self.eraser_brush_size = 10.0 # Default eraser size
        self.current_crop_item = None      # Item being cropped
        self.crop_overlay_rect = None    # Visual crop rectangle QGraphicsRectItem
        self.active_crop_handles = []    # Handles for the crop_overlay_rect

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
        self.pen_color_label.setVisible(False) # Hide by default
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
        selected_items = self.scene.selectedItems()
        self._remove_resize_handles() # Clear old handles first

        if selected_items:
            self.selected_item = selected_items[0] # Assuming single selection for now
            # Create resize handles for the newly selected item
            # We only add handles if the select tool is active, or perhaps always show them?
            # For now, let's always show them on selection.
            if isinstance(self.selected_item, (QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPixmapItem)):
                 # For Ellipse and Pixmap, ensure they have a rect() method or adapt handle creation
                 # QGraphicsPixmapItem has boundingRect(), QGraphicsEllipseItem has rect()
                self._create_resize_handles_for_item(self.selected_item)
            print(f"Selected: {self.selected_item}")
        else:
            self.selected_item = None
            print("Selection cleared")

        self._update_properties_panel_for_selection()

    def update_shape_tool_button_text(self):
        if self.current_tool in ["rectangle", "ellipse", "line", "pen"] and self.current_shape_tool_action:
            self.shape_tool_button.setText(self.current_shape_tool_action.text())
        else:
            # Default or if a non-shape tool is active but we want to show last shape
            self.shape_tool_button.setText(self.current_shape_tool_action.text()) 

    def set_tool(self, tool_name):
        # Temporarily disconnect pen width spinbox to prevent unintended updates during tool switch
        if hasattr(self, 'pen_width_spinbox'): # Check if it exists
            try: self.pen_width_spinbox.valueChanged.disconnect(self.on_pen_width_changed) 
            except RuntimeError: pass # If not connected, fine

        self.current_tool = tool_name
        print(f"Tool changed to: {self.current_tool}")

        # Uncheck main tools if a shape tool is selected from dropdown
        if tool_name in ["rectangle", "ellipse", "line", "pen"]:
            for action in self.main_tool_actions_group:
                action.setChecked(False)
            # Update current_shape_tool_action based on tool_name
            if tool_name == "rectangle": self.current_shape_tool_action = self.shape_menu.actions()[0]
            elif tool_name == "ellipse": self.current_shape_tool_action = self.shape_menu.actions()[1]
            elif tool_name == "line": self.current_shape_tool_action = self.shape_menu.actions()[2]
            elif tool_name == "pen": self.current_shape_tool_action = self.shape_menu.actions()[3] # Assuming Pen is 4th
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
                self.view.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                self.view.setInteractive(True)
                self.view.setCursor(Qt.CursorShape.ArrowCursor)
            elif self.current_tool == "hand":
                self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
                self.view.setInteractive(False) # View handles panning, item interaction off
                self.view.setCursor(Qt.CursorShape.OpenHandCursor)
            elif self.current_tool == "eraser":
                self.view.setDragMode(QGraphicsView.DragMode.NoDrag) # We will handle erase path manually
                self.view.setInteractive(False) # Items should not be selectable/movable by eraser tool itself
                self.view.setCursor(Qt.CursorShape.CrossCursor) # Placeholder, can be custom later
        
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
        self._remove_resize_handles() # Clear existing before creating new
        
        theme_colors = self.current_theme_colors # Use current theme for handles

        # Determine rect based on item type
        if isinstance(parent_item, QGraphicsPixmapItem):
            item_rect = parent_item.boundingRect() # For pixmaps, boundingRect is in item's coords
        elif isinstance(parent_item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            item_rect = parent_item.rect() # For shapes, rect is fine
        else:
            return # No handles for other types yet

        # SE handle (bottom-right)
        se_pos = QPointF(item_rect.right() - HANDLE_SIZE / 2, item_rect.bottom() - HANDLE_SIZE / 2)
        se_handle = QGraphicsRectItem(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent_item)
        se_handle.setPos(se_pos)
        se_handle.setBrush(theme_colors["selected_handle_fill"])
        se_handle.setPen(QPen(theme_colors["selected_handle_outline"]))
        se_handle.is_resize_handle = True
        se_handle.handle_type = "se"
        self.active_resize_handles.append(se_handle)

    def _update_resize_handles_for_item(self, parent_item):
        if not self.active_resize_handles or not parent_item: return
        
        # Determine rect based on item type
        if isinstance(parent_item, QGraphicsPixmapItem):
            item_rect = parent_item.boundingRect()
        elif isinstance(parent_item, (QGraphicsRectItem, QGraphicsEllipseItem)):
            item_rect = parent_item.rect()
        else:
            return
            
        for handle in self.active_resize_handles:
            if handle.handle_type == "se":
                handle.setPos(item_rect.right() - HANDLE_SIZE / 2, item_rect.bottom() - HANDLE_SIZE / 2)
                # Also update handle colors in case theme changed while selected
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
        self.pen_color_label.setVisible(False) # Hide by default
        self.change_pen_color_button.setVisible(False)
        self.current_pen_color_preview.setVisible(False)
        self.pen_width_label.setVisible(False)
        self.pen_width_spinbox.setVisible(False)

        if self.selected_item:
            item = self.selected_item
            item_type_str = "Unknown"
            theme_colors = self.current_theme_colors # For contrasting text

            # Default visibility for pen tool's own properties (when an item is selected but it's not the pen tool itself active)
            self.pen_color_label.setVisible(False)
            self.change_pen_color_button.setVisible(False)
            self.change_pen_color_button.setText("Change Pen Color") # Reset text
            self.current_pen_color_preview.setVisible(False)
            self.pen_width_label.setVisible(False)
            self.pen_width_spinbox.setVisible(False)

            if isinstance(item, QGraphicsRectItem):
                item_type_str = "Rectangle"
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
            elif isinstance(item, QGraphicsEllipseItem):
                item_type_str = "Ellipse"
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
            elif isinstance(item, QGraphicsLineItem):
                item_type_str = "Line"
                self.outline_color_button.setVisible(True)
                self.current_outline_color_label.setVisible(True)
                self.current_fill_color_label.setText("Fill: N/A")
                self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()};")
                outline_color = item.pen().color()
                self.current_outline_color_label.setText(f"Outline: {outline_color.name()}")
                self.current_outline_color_label.setStyleSheet(f"background-color: {outline_color.name()}; color: {self.get_contrasting_text_color(outline_color, theme_colors).name()}")
            elif isinstance(item, QGraphicsPathItem) and hasattr(item, 'item_type') and item.item_type == 'pen_stroke':
                item_type_str = "Pen Stroke"
                self.pen_color_label.setVisible(True)
                self.change_pen_color_button.setVisible(True)
                self.change_pen_color_button.setText("Change Stroke Color") # Relabel for context
                self.current_pen_color_preview.setVisible(True)
                self.current_pen_color_preview.setStyleSheet(f"color: {item.pen().color().name()}; font-size: 20px;")
                self.pen_width_label.setVisible(True)
                self.pen_width_spinbox.setVisible(True)
                
                # Update spinbox value for selected stroke without triggering its own signal:
                self.pen_width_spinbox.blockSignals(True)
                self.pen_width_spinbox.setValue(int(item.pen().widthF()))
                self.pen_width_spinbox.blockSignals(False)

                # Hide other irrelevant properties
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

            elif isinstance(item, QGraphicsPixmapItem):
                item_type_str = "Image"
                self.remove_bg_button.setVisible(True)
                self.current_fill_color_label.setText("Fill: N/A")
                self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()};")
                self.current_outline_color_label.setText("Outline: N/A")
                self.current_outline_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()};")
            
            # Show image-specific properties if it's one of our managed image items
            if hasattr(item, 'pil_original_image'):
                self.remove_bg_button.setVisible(True)
                self.brightness_label.setVisible(True)
                self.brightness_slider.setVisible(True)
                self.brightness_value_label.setVisible(True)
                
                self.start_crop_button.setVisible(True)
                self.apply_crop_button.setVisible(self.current_crop_item == item)
                self.cancel_crop_button.setVisible(self.current_crop_item == item)
                
                if not self.current_crop_item:
                    slider_val = int(item.current_brightness_factor * 100)
                    self.brightness_slider.setValue(slider_val)
                    self.brightness_value_label.setText(f"{slider_val}%")
            else: # Not an image or not one we manage PIL for, or not selected
                self.remove_bg_button.setVisible(False)
                self.brightness_label.setVisible(False)
                self.brightness_slider.setVisible(False)
                self.brightness_value_label.setVisible(False)
                self.start_crop_button.setVisible(False)
                self.apply_crop_button.setVisible(False)
                self.cancel_crop_button.setVisible(False)
            
            self.prop_label.setText(f"Selected: {item_type_str}")
        else:
            self.prop_label.setText("Selected: None")
            # Reset color labels for consistency when no selection
            theme_colors = self.current_theme_colors
            self.current_fill_color_label.setText("Fill: N/A")
            self.current_fill_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")
            self.current_outline_color_label.setText("Outline: N/A")
            self.current_outline_color_label.setStyleSheet(f"color: {theme_colors['text_color'].name()}; background-color: transparent;")

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

                self.scene.addItem(image_item)
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
        if not self.selected_item or not isinstance(self.selected_item, QGraphicsPixmapItem) or not hasattr(self.selected_item, 'pil_original_image'):
            QMessageBox.warning(self, "Cannot Crop", "Please select an image loaded by the application to crop.")
            return

        if self.current_crop_item: # Already cropping another item? Or re-clicked on same item?
            if self.current_crop_item == self.selected_item:
                # Clicked "Crop Image" again for the item already in crop mode - do nothing or treat as cancel?
                # For now, let's assume this state shouldn't be easily reachable if UI updates correctly.
                return 
            else:
                # Switched selection while an old crop was active - cancel old one first
                self.exit_crop_mode(apply_changes=False) 

        self.current_crop_item = self.selected_item
        self._remove_resize_handles() # Remove item resize handles, as we'll use crop handles
        self.selected_item.setSelected(False) # Deselect to avoid confusion with item move/resize
        self.selected_item.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, False) # Disable moving base image

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
        # Similar to _create_resize_handles_for_item but for self.crop_overlay_rect
        # and handles should be parented to self.crop_overlay_rect or self.current_crop_item
        self._remove_crop_handles() # Clear any existing crop handles
        if not self.crop_overlay_rect or not self.current_crop_item:
            return

        parent_for_handles = self.crop_overlay_rect # Handles are children of the crop rect
        rect_to_handle = self.crop_overlay_rect.rect() # This is in crop_overlay_rect's local coords (0,0 top-left)

        # SE handle (bottom-right of the crop_overlay_rect)
        se_pos = QPointF(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2)
        se_handle = QGraphicsRectItem(0, 0, HANDLE_SIZE, HANDLE_SIZE, parent_for_handles)
        se_handle.setPos(se_pos)
        se_handle.setBrush(self.current_theme_colors["selected_handle_fill"]) # Use theme colors
        se_handle.setPen(QPen(self.current_theme_colors["selected_handle_outline"], 1))
        se_handle.is_crop_handle = True 
        se_handle.handle_type = "se_crop"
        se_handle.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False) # Prevent movement via item dragging
        self.active_crop_handles.append(se_handle)
        # Add other handles (nw, ne, sw, n, s, e, w) here later for full cropping

    def _update_crop_handles(self):
        if not self.active_crop_handles or not self.crop_overlay_rect: return
        rect_to_handle = self.crop_overlay_rect.rect()
        for handle in self.active_crop_handles:
            if handle.handle_type == "se_crop":
                handle.setPos(rect_to_handle.right() - HANDLE_SIZE / 2, rect_to_handle.bottom() - HANDLE_SIZE / 2)
                handle.setBrush(self.current_theme_colors["selected_handle_fill"])
                handle.setPen(QPen(self.current_theme_colors["selected_handle_outline"], 1))

    def _remove_crop_handles(self):
        for handle in self.active_crop_handles:
            if handle.scene(): self.scene.removeItem(handle)
        self.active_crop_handles.clear()

    def exit_crop_mode(self, apply_changes=False):
        if not self.current_crop_item:
            return
        
        item_was_cropped = self.current_crop_item

        if apply_changes and self.crop_overlay_rect:
            # 1. Get crop rectangle in item's local coordinates.
            # crop_overlay_rect is already a child, its rect() is what we need.
            crop_box_item_coords = self.crop_overlay_rect.rect()

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
                # Fall through to cleanup, effectively canceling the visual crop mode changes.
        
        # Cleanup UI
        if self.crop_overlay_rect:
            self.scene.removeItem(self.crop_overlay_rect) # It's a child, but remove from scene explicitly
            self.crop_overlay_rect = None # This should also remove its children (handles)
        self._remove_crop_handles()
        
        item_was_cropped.setFlag(QGraphicsPixmapItem.GraphicsItemFlag.ItemIsMovable, True) # Re-enable moving
        # Re-select the item to restore normal selection behavior and show resize handles
        item_was_cropped.setSelected(True) 
        # on_scene_selection_changed will be triggered, which should call _create_resize_handles_for_item

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CanvasWindow()
    window.show()
    sys.exit(app.exec()) 