#!/usr/bin/env python

import sys
import rospy

import moveit_commander
from moveit_msgs.msg import CollisionObject, PlanningScene
from moveit_msgs.srv import ApplyPlanningScene
from geometry_msgs.msg import PoseStamped
from shape_msgs.msg import SolidPrimitive
from sensor_msgs.msg import PointCloud2

from clf_object_recognition_msgs.srv  import Detect3D
from clf_grasping_msgs.srv import CloudToCollision
from clf_object_recognition_msgs.msg import BoundingBox3DArray

from geometry_msgs.msg import Point32, Pose, Point, Quaternion, PoseStamped

import tf2_geometry_msgs

import tf2_ros

def classify_3d():
    srv = "/object_merger/detect_objects"
    print("waiting for service " + srv)
    rospy.wait_for_service(srv)
    print("detecting objects...")
    try:
        client = rospy.ServiceProxy(srv, Detect3D)
        resp = client()
        print("got " + str(len(resp.detections)) + " objects classified")
        return resp.detections
    except rospy.ServiceException, e:
        print "Service call failed: %s"%e

# Bug: this seems to clear the the planning scene (including the acm)
def add_to_planning_scene(objects):
    scene_diff = PlanningScene()
    scene_diff.world.collision_objects = objects
    scene_diff.is_diff = False
    srv = "/apply_planning_scene"
    print("waiting for service " + srv)
    rospy.wait_for_service(srv)
    #print("adding " + str(len(objects)) + " objects ...")
    try:
        apply = rospy.ServiceProxy(srv, ApplyPlanningScene)
        #print(scene_diff)
        resp = apply(scene_diff)
        return resp
    except rospy.ServiceException, e:
        print "Service call failed: %s"%e

def helper_make_cylinder(name, pose, height, radius):
        co = CollisionObject()
        co.operation = CollisionObject.ADD
        co.id = name
        co.header = pose.header
        cylinder = SolidPrimitive()
        cylinder.type = SolidPrimitive.CYLINDER
        cylinder.dimensions = [height, radius]
        co.primitives = [cylinder]
        co.primitive_poses = [pose.pose]
        return co

def add_to_planning_scene2(objects):
    print("add_to_planning_scene2: got "+str(len(objects))+" objects")
    scene = moveit_commander.PlanningSceneInterface()
    rospy.sleep(2)
    for obj in objects:
        obj.operation=obj.ADD
        print(obj)
        #scene._pub_co.publish(obj)
        p = PoseStamped()
        p.header = obj.header
        p.pose = obj.primitive_poses[0]
        #scene.add_box(obj.id, p, size=(obj.primitives[0].dimensions[0], obj.primitives[0].dimensions[1], obj.primitives[0].dimensions[1]))
        if obj.primitives[0].type==obj.primitives[0].BOX:
            scene.add_box(obj.id, p, size=(obj.primitives[0].dimensions[0], obj.primitives[0].dimensions[1], obj.primitives[0].dimensions[2]))
        elif obj.primitives[0].type==obj.primitives[0].CYLINDER:
            #the real add_cylinder function is not available in kinetic
            #scene.add_cylinder(obj.id, obj.primitive_poses[0], obj.primitives[0].dimensions[0], obj.primitives[0].dimensions[1])
            scene._pub_co.publish(helper_make_cylinder(obj.id, p, obj.primitives[0].dimensions[0], obj.primitives[0].dimensions[1]))
        else:
            print("add_to_planning_scene: unknown shape: "+str(obj.primitives[0].type))

def filter_frames(detections):
    print("filtering detections with empty frames")
    filtered = []
    for detect3d in detections:
        if detect3d.header.frame_id is "":
            print("filtered empty frame id object")
            continue
        filtered.append(detect3d)

    return filtered

def filter_poses(detections):
    print("filtering detection poses")
    filtered = []
    for detect3d in detections:

        print("bounding box: "+str(detect3d.bbox))

        pose = PoseStamped()
        pose.pose = detect3d.bbox.center
        pose.header = detect3d.header
        # print("pose: \n" + str(pose))
        transform = getTFPos(pose.header.frame_id,"map")
        # print("transform: \n" + str(transform))
        map_center = tf2_geometry_msgs.do_transform_pose(pose, transform)
        # print("center point: \n" + str(map_center))
        surface = map_center.pose.position.z + detect3d.bbox.size.z

        if map_center < 0:
            print("filtered negative center heigth")
            continue

        print("surface@: " + str(surface))
        if surface < 0.2:
            print("filtered low surface heigth < 0.3m")
            continue
        
        

        filtered.append(detect3d)
    return filtered

    
    pose.position.x = tf_Stamped.transform.translation.x
    pose.position.y = tf_Stamped.transform.translation.y
    pose.position.z = tf_Stamped.transform.translation.z
    pose.orientation = tf_Stamped.transform.rotation


def send_clouds(detections):
    print("publishing clouds")
    for detect3d in detections:
        #print(detect3d.source_cloud)
        pub.publish(detect3d.source_cloud)

def send_boxes(objects):
    print("publishing boxes")
    boxes = BoundingBox3DArray()
    for detect3d in objects:
        boxes.header = detect3d.header
        boxes.boxes.append(detect3d.bbox)
    
    pubbox.publish(boxes)

def fit_objects(detections, shapes = []):
    co_objects = []
    i = 1
    srv = "/cloud_to_co"
    print("waiting for service " + srv)
    rospy.wait_for_service(srv)
    print("fitting objects ...")
    client = rospy.ServiceProxy(srv, CloudToCollision)
    for detect3d in detections:
        objectid = ""
        if len(detect3d.results) > 0:
            for hyp in detect3d.results:
                objectid = objectid + str(hyp.id) + ";"
        else:
            objectid = "unknown" + str(i)
            i += 1
        print(" fitting object: " + objectid)
        try:
            resp = client(shapes,detect3d.source_cloud)
            co = resp.collision_object
            
            # Fill co
            co.id = objectid
            #co.operation = CollisionObject.ADD
            co.header = detect3d.source_cloud.header

            co_objects.append(co)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e
    print("fitting finished")
    return co_objects

def getTFPos(frame_orig, frame_dest):
        """
        use TF2 to get the current pos of a frame
        """
        rospy.logdebug("getTFPos source_frame %s target_frame %s, target_frame", frame_orig, frame_dest)
        if tf_Buffer.can_transform(frame_dest, frame_orig , rospy.Time(), rospy.Duration(1.0)):
            try:
                tf_Stamped = tf_Buffer.lookup_transform(frame_dest, frame_orig, rospy.Time(0))
                return tf_Stamped
            except (tf2_ros.LookupException, tf2_ros.ConnectivityException) as e:
                rospy.logdebug("getTFPos lookup frame orig " + str(frame_orig) + " to " + str(frame_dest) + " transform not found ")
                rospy.logdebug(e)
                return None
            except tf2_ros.ExtrapolationException, e:
                rospy.logdebug("getTFPos extrapolation frame orig " + str(frame_orig) + " to " + str(frame_dest) + " transform not found ")
                rospy.logdebug(e)
                return None
        else:
            rospy.logdebug("getTFPos frame dest " + str(frame_dest) + " doest not exist")
            return None

if __name__ == "__main__":

    rospy.init_node('clouds', anonymous=True)

    # TF listener
    tf_Buffer = tf2_ros.Buffer()
    tf_listener = tf2_ros.TransformListener(tf_Buffer)
    pub = rospy.Publisher('/clouds', PointCloud2, queue_size=10)
    pubbox = rospy.Publisher('/bbs', BoundingBox3DArray, queue_size=10)

    classes = classify_3d()
    classes = filter_frames(classes)
    classes = filter_poses(classes)
    send_clouds(classes)
    send_boxes(classes)
    co_objects = fit_objects(classes)
    add_to_planning_scene2(co_objects)
    #add_to_planning_scene(co_objects)
