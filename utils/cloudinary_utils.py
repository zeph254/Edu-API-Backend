import cloudinary.uploader
from werkzeug.utils import secure_filename
import os

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image_to_cloudinary(file, folder="profile_pictures"):
    """
    Uploads an image to Cloudinary
    Returns: dict with 'public_id' and 'url'
    """
    if not file or file.filename == '':
        return None
        
    if not allowed_file(file.filename):
        raise ValueError("Invalid file type. Only images are allowed.")
    
    try:
        # Upload the image to Cloudinary
        result = cloudinary.uploader.upload(
            file,
            folder=folder,
            resource_type="image"
        )
        return {
            'public_id': result['public_id'],
            'url': result['secure_url']
        }
    except Exception as e:
        raise Exception(f"Failed to upload image: {str(e)}")

def delete_image_from_cloudinary(public_id):
    """
    Deletes an image from Cloudinary
    """
    try:
        return cloudinary.uploader.destroy(public_id)
    except Exception as e:
        raise Exception(f"Failed to delete image: {str(e)}")