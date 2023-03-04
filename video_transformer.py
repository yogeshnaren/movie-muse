import cv2

# Load the video file
video_path = input("Enter the path to the video file: ")
video = cv2.VideoCapture(video_path)

# Load the image file
image_path = input("Enter the path to the image file: ")
image = cv2.imread(image_path)

# Resize the image to match the video size
image = cv2.resize(image, (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))))

# Convert the image to the LAB color space
image_lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

# Extract the L, A, and B channels of the image
image_l, image_a, image_b = cv2.split(image_lab)

# Get the frame size and frame rate of the video
frame_size = (int(video.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video.get(cv2.CAP_PROP_FRAME_HEIGHT)))
fps = video.get(cv2.CAP_PROP_FPS)

# Create a VideoWriter object to save the transformed video
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Change this to the codec you want to use
out = cv2.VideoWriter('transformed_video.mp4', fourcc, fps, frame_size)

# Loop through each frame in the video
while True:
    # Read the next frame from the video
    ret, frame = video.read()

    # If there are no more frames, break out of the loop
    if not ret:
        break

    # Convert the frame to the LAB color space
    frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

    # Extract the L, A, and B channels of the frame
    frame_l, frame_a, frame_b = cv2.split(frame_lab)

    # Combine the L channel of the image and the A and B channels of the frame
    merged_lab = cv2.merge((image_l, frame_a, frame_b))

    # Convert the merged LAB image back to the BGR color space
    merged_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)

    # Write the transformed frame to the output video
    out.write(merged_bgr)

    # Display the transformed frame
    cv2.imshow("Transformed Frame", merged_bgr)

    # Wait for a key press and check if the user wants to quit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the video, release the VideoWriter, and close all windows
video.release()
out.release()
cv2.destroyAllWindows()
